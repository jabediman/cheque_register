# Copyright (c) 2026, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, flt, getdate, nowdate

from erpnext.accounts.party import get_party_account
from erpnext.accounts.utils import get_account_currency

# Bangladesh Bank rule: a cheque is valid for 6 months from the date on the cheque
CHEQUE_VALIDITY_MONTHS = 6
REMINDER_DAYS = 2  # alert this many days before the cheque date
EXPIRY_WARNING_DAYS = 14  # alert when a held cheque is this close to going stale



def get_company_cheque_settings(company):
    settings = get_company_cheque_settings(self.company)
    for row in (settings.get("company_accounts") or settings.get("default_cheque_accounts") or settings.get("accounts") or []):
        if row.get("company") == company:
            return row
    # যদি কোনো চাইল্ড টেবিলে company ম্যাচ করে (যেকোনো টেবিল ফিল্ডনাম হোক না কেন)
    for df in settings.meta.get_table_fields():
        for row in (settings.get(df.fieldname) or []):
            if row.get("company") == company:
                return row
    return settings

class ChequeRegister(Document):
	# ------------------------------------------------------------------
	# Lifecycle hooks
	# ------------------------------------------------------------------
	def before_insert(self):
		self.status = "Received" if self.cheque_type == "Collection Cheque" else "Issued"

	def validate(self):
		self.set_defaults()
		self.validate_amount_and_dates()
		self.validate_duplicate()
		self.validate_payment_entry()
		self.validate_references()
		self.calculate_totals()
		self.set_party_name()

	def set_defaults(self):
		if not self.party_type:
			self.party_type = "Customer" if self.cheque_type == "Collection Cheque" else "Supplier"
		self.is_post_dated = 1 if getdate(self.cheque_date) > getdate(self.transaction_date) else 0

	def validate_amount_and_dates(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero."))

		if add_months(getdate(self.cheque_date), CHEQUE_VALIDITY_MONTHS) < getdate(self.transaction_date):
			frappe.throw(
				_("This cheque is stale: more than {0} months have passed since the cheque date.").format(
					CHEQUE_VALIDITY_MONTHS
				)
			)

	def validate_duplicate(self):
		duplicate = frappe.db.exists(
			"Cheque Register",
			{
				"cheque_type": self.cheque_type,
				"cheque_bank": self.cheque_bank,
				"cheque_no": self.cheque_no,
				"name": ["!=", self.name],
				"status": ["not in", ["Cancelled", "Dishonoured"]],
			},
		)
		if duplicate:
			frappe.throw(
				_("Cheque {0} of {1} is already registered in {2}.").format(
					frappe.bold(self.cheque_no), self.cheque_bank, frappe.bold(duplicate)
				)
			)

	def validate_payment_entry(self):
		if not self.payment_entry or self.status not in ("Received", "Issued"):
			return

		pe = frappe.db.get_value(
			"Payment Entry",
			self.payment_entry,
			["party_type", "party", "paid_amount", "payment_type", "docstatus", "company"],
			as_dict=True,
		)
		if not pe:
			return
		if pe.docstatus == 2:
			frappe.throw(_("Payment Entry {0} is cancelled.").format(self.payment_entry))
		if pe.party != self.party or pe.party_type != self.party_type:
			frappe.throw(_("Party in Payment Entry {0} does not match this cheque.").format(self.payment_entry))
		expected = "Receive" if self.cheque_type == "Collection Cheque" else "Pay"
		if pe.payment_type != expected:
			frappe.throw(_("Payment Entry {0} must be of type {1}.").format(self.payment_entry, expected))
		if abs(flt(pe.paid_amount) - flt(self.amount)) > 0.005:
			frappe.throw(_("Amount in Payment Entry {0} does not match the cheque amount.").format(self.payment_entry))

	def _invoice_meta(self):
		"""(invoice doctype, party field on that doctype) for this cheque's party type."""
		if self.party_type == "Customer":
			return "Sales Invoice", "customer"
		return "Purchase Invoice", "supplier"

	def validate_references(self):
		if self.payment_entry:
			# Allocation is locked once the Payment Entry exists; invoices may have been paid since
			return

		invoice_doctype, party_field = self._invoice_meta()
		seen = set()
		for row in self.get("references") or []:
			row.reference_doctype = invoice_doctype
			if row.reference_name in seen:
				frappe.throw(_("Row {0}: invoice {1} is listed twice.").format(row.idx, row.reference_name))
			seen.add(row.reference_name)

			if flt(row.allocated_amount) <= 0:
				frappe.throw(_("Row {0}: allocated amount must be greater than zero.").format(row.idx))

			inv = frappe.db.get_value(
				invoice_doctype,
				row.reference_name,
				[party_field, "company", "docstatus", "posting_date", "grand_total", "outstanding_amount"],
				as_dict=True,
			)
			if not inv or inv.docstatus != 1:
				frappe.throw(_("Row {0}: {1} {2} is not a submitted invoice.").format(row.idx, invoice_doctype, row.reference_name))
			if inv.get(party_field) != self.party or inv.company != self.company:
				frappe.throw(_("Row {0}: {1} does not belong to {2} / {3}.").format(row.idx, row.reference_name, self.party, self.company))

			row.posting_date = inv.posting_date
			row.invoice_total = inv.grand_total
			row.outstanding_amount = inv.outstanding_amount
			if flt(row.allocated_amount) > flt(inv.outstanding_amount) + 0.005:
				frappe.throw(
					_("Row {0}: allocated amount exceeds the outstanding amount ({1}) of {2}.").format(
						row.idx, flt(inv.outstanding_amount), row.reference_name
					)
				)

	def calculate_totals(self):
		total = sum(flt(r.allocated_amount) for r in self.get("references") or [])
		if total > flt(self.amount) + 0.005:
			frappe.throw(
				_("Total allocated ({0}) cannot exceed the cheque amount ({1}).").format(total, flt(self.amount))
			)
		self.total_allocated = total
		self.unallocated_amount = flt(self.amount) - total

	@frappe.whitelist()
	def get_outstanding_invoices(self):
		"""Open invoices of the party, oldest first, pre-allocated up to the cheque amount."""
		self.check_permission("read")
		if not (self.party and self.company):
			frappe.throw(_("Select Company and Party first."))

		invoice_doctype, party_field = self._invoice_meta()
		invoices = frappe.get_all(
			invoice_doctype,
			filters={
				party_field: self.party,
				"company": self.company,
				"docstatus": 1,
				"outstanding_amount": [">", 0],
			},
			fields=["name", "posting_date", "grand_total", "outstanding_amount"],
			order_by="posting_date asc, creation asc",
		)

		remaining = flt(self.amount)
		rows = []
		for inv in invoices:
			allocated = min(remaining, flt(inv.outstanding_amount)) if remaining > 0 else 0
			remaining -= allocated
			rows.append(
				{
					"reference_doctype": invoice_doctype,
					"reference_name": inv.name,
					"posting_date": inv.posting_date,
					"invoice_total": inv.grand_total,
					"outstanding_amount": inv.outstanding_amount,
					"allocated_amount": allocated,
				}
			)
		return rows

	def set_party_name(self):
		field = {"Customer": "customer_name", "Supplier": "supplier_name"}.get(self.party_type)
		if field and self.party:
			self.party_name = frappe.db.get_value(self.party_type, self.party, field)

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------
	def _require(self, cheque_type, *statuses):
		if self.cheque_type != cheque_type or self.status not in statuses:
			frappe.throw(
				_("This action needs a {0} cheque with status {1}.").format(
					cheque_type, " / ".join(statuses)
				)
			)

	def _make_journal_entry(self, posting_date, rows, remark, with_cheque_info=True):
		"""rows: list of (account, debit, credit). Returns submitted Journal Entry name."""
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Bank Entry"
		je.company = self.company
		je.posting_date = posting_date
		je.custom_remark = 1
		je.user_remark = remark
		if with_cheque_info:
			je.cheque_no = self.cheque_no
			je.cheque_date = self.cheque_date
		for account, debit, credit in rows:
			je.append(
				"accounts",
				{
					"account": account,
					"debit_in_account_currency": flt(debit),
					"credit_in_account_currency": flt(credit),
						"user_remark": remark,
				},
			)
		je.insert()
		je.submit()
		return je.name

	# ------------------------------------------------------------------
	# Actions (called from the form buttons)
	# ------------------------------------------------------------------
	def on_submit(self):
		if not self.payment_entry:
			self.make_payment_entry(submit=1)

	def on_cancel(self):
		for jv_field in ["bank_charges_journal_entry", "dishonour_journal_entry", "clearance_journal_entry", "deposit_journal_entry"]:
			jv = self.get(jv_field)
			if jv and frappe.db.get_value("Journal Entry", jv, "docstatus") == 1:
				frappe.get_doc("Journal Entry", jv).cancel()
		if self.payment_entry and frappe.db.get_value("Payment Entry", self.payment_entry, "docstatus") == 1:
			pe = frappe.get_doc("Payment Entry", self.payment_entry)
			pe.flags.ignore_links = True
			pe.cancel()
		self.db_set("status", "Cancelled")

	@frappe.whitelist()
	def make_payment_entry(self, submit=1):
		"""Create the Payment Entry from this cheque and its invoice allocation table.
		submit=1 posts it immediately, submit=0 leaves a draft."""
		self.check_permission("write")
		self.validate_references()
		self.calculate_totals()
		if self.payment_entry:
			frappe.throw(_("Payment Entry {0} is already linked.").format(self.payment_entry))
		self._require(self.cheque_type, "Received", "Issued")

		incoming = self.cheque_type == "Collection Cheque"
		party_account = get_party_account(self.party_type, self.party, self.company)

		if incoming:
			paid_from, paid_to = party_account, self.cheque_in_hand_account
			missing = _("Cheques in Hand Account")
		else:
			# With a PDC Payable account the bank balance only moves when the cheque is cleared
			paid_from, paid_to = self.pdc_payable_account or self.bank_account, party_account
			missing = _("Cheques Issued (PDC Payable) Account or Bank Account (GL)")
		if not (paid_from and paid_to):
			frappe.throw(_("Please set {0} first.").format(missing))

		pe = frappe.new_doc("Payment Entry")
		pe.payment_type = "Receive" if incoming else "Pay"
		pe.company = self.company
		pe.posting_date = self.transaction_date
		pe.mode_of_payment = self.mode_of_payment
		pe.party_type = self.party_type
		pe.party = self.party
		pe.paid_from = paid_from
		pe.paid_to = paid_to
		pe.paid_from_account_currency = get_account_currency(paid_from)
		pe.paid_to_account_currency = get_account_currency(paid_to)
		pe.source_exchange_rate = 1
		pe.target_exchange_rate = 1
		pe.paid_amount = self.amount
		pe.received_amount = self.amount
		pe.reference_no = self.cheque_no
		pe.reference_date = self.cheque_date
		pe.remarks = _("Cheque {0}, {1}").format(self.cheque_no, self.cheque_bank)

		party_account_currency = get_account_currency(party_account)
		for row in self.get("references") or []:
			details = self._reference_details(row, party_account_currency)
			pe.append(
				"references",
				{
					"reference_doctype": row.reference_doctype,
					"reference_name": row.reference_name,
					"total_amount": details.total_amount,
					"outstanding_amount": details.outstanding_amount,
					"allocated_amount": row.allocated_amount,
					"exchange_rate": details.exchange_rate or 1,
					"due_date": details.due_date,
					"bill_no": details.bill_no,
				},
			)

		pe.insert()
		if int(submit or 0):
			pe.submit()

		self.payment_entry = pe.name
		self.save()
		return pe.name

	def _reference_details(self, row, party_account_currency):
		"""Invoice amounts as Payment Entry expects them (uses ERPNext's own helper when present)."""
		try:
			from erpnext.accounts.doctype.payment_entry.payment_entry import get_reference_details
		except ImportError:
			get_reference_details = None

		if get_reference_details:
			return frappe._dict(
				get_reference_details(
					row.reference_doctype, row.reference_name, party_account_currency, self.party_type, self.party
				)
			)

		inv = frappe.db.get_value(
			row.reference_doctype, row.reference_name, ["grand_total", "outstanding_amount", "due_date"], as_dict=True
		)
		return frappe._dict(
			total_amount=inv.grand_total,
			outstanding_amount=inv.outstanding_amount,
			due_date=inv.due_date,
			exchange_rate=1,
			bill_no=None,
		)

	@frappe.whitelist()
	def mark_deposited(self, deposit_date=None):
		"""Cheque handed over to the bank: Dr Bank (or Under Collection) / Cr Cheques in Hand."""
		self.check_permission("write")
		self._require("Collection Cheque", "Received")

		deposit_date = getdate(deposit_date or nowdate())
		if getdate(self.cheque_date) > deposit_date:
			frappe.throw(_("Post-dated cheque cannot be deposited before the cheque date ({0}).").format(self.cheque_date))
		if add_months(getdate(self.cheque_date), CHEQUE_VALIDITY_MONTHS) < deposit_date:
			frappe.throw(_("This cheque is stale (older than {0} months).").format(CHEQUE_VALIDITY_MONTHS))
		if not (self.cheque_in_hand_account and self.bank_account):
			frappe.throw(_("Set Cheques in Hand Account and Bank Account (GL) first."))

		target = self.under_collection_account or self.bank_account
		self.deposit_journal_entry = self._make_journal_entry(
			deposit_date,
			[(target, self.amount, 0), (self.cheque_in_hand_account, 0, self.amount)],
			_("Cheque {0} deposited | Party: {1} | Bank: {2} ({3})").format(self.cheque_no, self.party_name or self.party or "", self.cheque_bank, self.name),
		)
		self.deposit_date = deposit_date
		self.status = "Deposited"
		self.save()

	@frappe.whitelist()
	def mark_cleared(self, clearance_date=None):
		"""Bank confirmed the money. Creates Clearance Journal Entry directly from Received or Deposited."""
		self.check_permission("write")
		clearance_date = getdate(clearance_date or nowdate())

		if self.cheque_type == "Collection Cheque":
			self._require("Collection Cheque", "Received", "Deposited")
			if not self.bank_account:
				frappe.throw(_("Set Deposit / Bank Account (GL) first."))
			if not self.cheque_in_hand_account:
				frappe.throw(_("Set Cheques in Hand Account first."))

			if not self.deposit_journal_entry:
				source_acc = self.under_collection_account if (self.status == "Deposited" and self.under_collection_account) else self.cheque_in_hand_account
				self.clearance_journal_entry = self._make_journal_entry(
					clearance_date,
					[(self.bank_account, self.amount, 0), (source_acc, 0, self.amount)],
					_("Cheque {0} cleared | Party: {1} | Bank: {2} ({3})").format(self.cheque_no, self.party_name or self.party or "", self.cheque_bank, self.name),
				)
				frappe.db.set_value("Journal Entry", self.clearance_journal_entry, "clearance_date", clearance_date)
			else:
				frappe.db.set_value("Journal Entry", self.deposit_journal_entry, "clearance_date", clearance_date)
		else:
			self._require("Payment Cheque", "Issued")
			if not self.payment_entry:
				frappe.throw(_("Create and submit the Payment Entry before marking this cheque cleared."))
			if frappe.db.get_value("Payment Entry", self.payment_entry, "docstatus") != 1:
				frappe.throw(_("Payment Entry {0} is not submitted.").format(self.payment_entry))

			if self.pdc_payable_account:
				if not self.bank_account:
					frappe.throw(_("Set Bank Account (GL) first."))
				self.clearance_journal_entry = self._make_journal_entry(
					clearance_date,
					[(self.pdc_payable_account, self.amount, 0), (self.bank_account, 0, self.amount)],
					_("Cheque {0} cleared | Party: {1} | Bank: {2} ({3})").format(self.cheque_no, self.party_name or self.party or "", self.cheque_bank, self.name),
				)
				frappe.db.set_value("Journal Entry", self.clearance_journal_entry, "clearance_date", clearance_date)
			else:
				frappe.db.set_value("Payment Entry", self.payment_entry, "clearance_date", clearance_date)

		self.clearance_date = clearance_date
		self.status = "Cleared"
		self.save()

	@frappe.whitelist()
	def mark_dishonoured(
		self,
		dishonour_date=None,
		reason=None,
		bank_charges=0,
		bank_charges_account=None,
		cancel_payment_entry=1,
	):
		"""Bounced cheque. Reverses the deposit (cheque goes back to Cheques in Hand); optionally
		cancels the Payment Entry so the invoices become outstanding again."""
		self.check_permission("write")
		self._require("Collection Cheque", "Deposited")

		dishonour_date = getdate(dishonour_date or nowdate())
		bank_charges = flt(bank_charges)
		if not reason:
			frappe.throw(_("Dishonour reason is required."))
		if bank_charges > 0 and not bank_charges_account:
			frappe.throw(_("Select the Bank Charges Account."))

		source = self.under_collection_account or self.bank_account
		rows = [(self.cheque_in_hand_account, self.amount, 0), (source, 0, self.amount)]
		if bank_charges > 0:
			rows += [(bank_charges_account, bank_charges, 0), (self.bank_account, 0, bank_charges)]

		self.dishonour_journal_entry = self._make_journal_entry(
			dishonour_date,
			rows,
			_("Cheque {0} dishonoured: {1}").format(self.cheque_no, reason),
			with_cheque_info=False,
		)

		if int(cancel_payment_entry or 0) and self.payment_entry:
			pe = frappe.get_doc("Payment Entry", self.payment_entry)
			if pe.docstatus == 1:
				pe.cancel()

		self.dishonour_date = dishonour_date
		self.dishonour_reason = reason
		self.bank_charges = bank_charges
		self.bank_charges_account = bank_charges_account
		self.status = "Dishonoured"
		self.save()

	@frappe.whitelist()
	def mark_cancelled(self):
		"""Cheque returned to the party / voided before any bank movement."""
		self.check_permission("cancel")
		self._require(self.cheque_type, "Received", "Issued")
		if self.docstatus == 1:
			self.cancel()
		else:
			self.status = "Cancelled"
			self.save()

# ----------------------------------------------------------------------
# Daily scheduler: reminder email
# ----------------------------------------------------------------------
def send_due_cheque_reminders():
	"""Hook this in hooks.py -> scheduler_events["daily"]."""
	today = getdate(nowdate())
	horizon = add_days(today, REMINDER_DAYS)
	fields = ["name", "cheque_no", "cheque_bank", "party_name", "cheque_date", "amount"]

	ready = frappe.get_all(
		"Cheque Register",
		filters={"cheque_type": "Collection Cheque", "status": "Received", "cheque_date": ["<=", horizon]},
		fields=fields,
		order_by="cheque_date",
	)
	paying = frappe.get_all(
		"Cheque Register",
		filters={"cheque_type": "Payment Cheque", "status": "Issued", "cheque_date": ["between", [today, horizon]]},
		fields=fields,
		order_by="cheque_date",
	)
	expiring = frappe.get_all(
		"Cheque Register",
		filters={
			"cheque_type": "Collection Cheque",
			"status": "Received",
			"cheque_date": ["<=", add_months(add_days(today, EXPIRY_WARNING_DAYS), -CHEQUE_VALIDITY_MONTHS)],
		},
		fields=fields,
		order_by="cheque_date",
	)
	if not (ready or paying or expiring):
		return

	recipients = _accounts_manager_emails()
	if not recipients:
		return

	def table(title, rows):
		if not rows:
			return ""
		body = "".join(
			"<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td style='text-align:right'>{4}</td></tr>".format(
				frappe.utils.get_link_to_form("Cheque Register", r.name, r.cheque_no),
				frappe.utils.escape_html(r.cheque_bank or ""),
				frappe.utils.escape_html(r.party_name or ""),
				frappe.utils.formatdate(r.cheque_date),
				frappe.utils.fmt_money(r.amount),
			)
			for r in rows
		)
		return (
			f"<h4>{title}</h4><table border='1' cellpadding='6' cellspacing='0'>"
			"<tr><th>Cheque No</th><th>Bank</th><th>Party</th><th>Cheque Date</th><th>Amount</th></tr>"
			f"{body}</table>"
		)

	message = (
		table(_("Incoming cheques ready / due to deposit"), ready)
		+ table(_("Outgoing cheques falling due - keep funds ready"), paying)
		+ table(_("Cheques about to become stale (6 months)"), expiring)
	)
	frappe.sendmail(recipients=recipients, subject=_("Cheque Register: daily due list"), message=message)


def _accounts_manager_emails():
	users = frappe.get_all(
		"Has Role", filters={"role": "Accounts Manager", "parenttype": "User"}, pluck="parent"
	)
	if not users:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ["in", users], "enabled": 1, "user_type": "System User"},
		pluck="email",
	)


@frappe.whitelist()
def get_gl_accounts_for_bank(company, bank):
	if not company or not bank:
		return []
	# ১. Bank Account মাস্টার থেকে ওই ব্যাংক ও কোম্পানির লিংক করা GL অ্যাকাউন্ট খোঁজা
	bank_clean = bank.replace("PLC", "").replace("Limited", "").strip()
	matched_banks = frappe.get_all("Bank", filters={"bank_name": ["like", f"%{bank_clean}%"]}, pluck="name")
	if not matched_banks:
		matched_banks = [bank]

	accounts = frappe.get_all(
		"Bank Account",
		filters={
			"company": company,
			"bank": ["in", matched_banks],
			"is_company_account": 1,
			"account": ["is", "set"]
		},
		pluck="account"
	)
	if accounts:
		return list(dict.fromkeys(accounts))

	# ২. Fallback: সরাসরি Chart of Accounts থেকে ব্যাংকের নাম মিলিয়ে GL অ্যাকাউন্ট খোঁজা
	return frappe.get_all(
		"Account",
		filters={
			"company": company,
			"account_type": "Bank",
			"is_group": 0,
			"account_name": ["like", f"%{bank_clean}%"]
		},
		pluck="name"
	)
