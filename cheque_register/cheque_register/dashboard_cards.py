# Copyright (c) 2026, Your Company and contributors
# For license information, please see license.txt

"""Number Card methods for the Cheque Management dashboard."""

import frappe
from frappe.utils import add_days, flt, getdate, nowdate

REPORT_ROUTE = ["query-report", "Cheque Due Schedule"]


def _total(cheque_type, statuses, cheque_date):
	rows = frappe.get_list(
		"Cheque Register",
		filters={"cheque_type": cheque_type, "status": ["in", statuses], "cheque_date": cheque_date},
		fields=["sum(amount) as total"],
	)
	return flt(rows[0].total) if rows else 0


def _card(value, route_options):
	return {
		"value": value,
		"fieldtype": "Currency",
		"route": REPORT_ROUTE,
		"route_options": route_options,
	}


@frappe.whitelist()
def outgoing_due_today():
	today = getdate(nowdate())
	value = _total("Payment Cheque", ["Issued"], today)
	return _card(value, {"cheque_type": "Payment Cheque", "from_date": str(today), "to_date": str(today)})


@frappe.whitelist()
def outgoing_due_7_days():
	today = getdate(nowdate())
	end = add_days(today, 7)
	value = _total("Payment Cheque", ["Issued"], ["between", [today, end]])
	return _card(value, {"cheque_type": "Payment Cheque", "from_date": str(today), "to_date": str(end)})


@frappe.whitelist()
def outgoing_past_date():
	today = getdate(nowdate())
	value = _total("Payment Cheque", ["Issued"], ["<", today])
	return _card(value, {"cheque_type": "Payment Cheque", "to_date": str(add_days(today, -1))})


@frappe.whitelist()
def incoming_ready_to_deposit():
	today = getdate(nowdate())
	value = _total("Collection Cheque", ["Received"], ["<=", today])
	return _card(value, {"cheque_type": "Collection Cheque", "status": "Received", "to_date": str(today)})
