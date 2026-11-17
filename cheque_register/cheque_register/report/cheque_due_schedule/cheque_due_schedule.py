# Copyright (c) 2026, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, flt, formatdate, getdate, nowdate

# statuses that still need action, per cheque type
PENDING = {"Payment Cheque": ["Issued"], "Collection Cheque": ["Received", "Deposited"]}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	cheque_type = filters.get("cheque_type") or "Payment Cheque"
	if cheque_type == "Collection Cheque":
		cheque_type = "Collection Cheque"
	elif cheque_type == "Payment Cheque":
		cheque_type = "Payment Cheque"
	statuses = [filters.status] if filters.get("status") else PENDING.get(cheque_type, PENDING["Collection Cheque"])

	conditions = {"cheque_type": cheque_type, "status": ["in", statuses]}
	if filters.get("company"):
		conditions["company"] = filters.company
	if filters.get("from_date") and filters.get("to_date"):
		conditions["cheque_date"] = ["between", [filters.from_date, filters.to_date]]
	elif filters.get("from_date"):
		conditions["cheque_date"] = [">=", filters.from_date]
	elif filters.get("to_date"):
		conditions["cheque_date"] = ["<=", filters.to_date]

	cheques = frappe.get_list(
		"Cheque Register",
		filters=conditions,
		fields=["name", "cheque_no", "cheque_date", "party_name", "cheque_bank", "amount", "status"],
		order_by="cheque_date asc, creation asc",
		limit_page_length=0,
	)

	today = getdate(nowdate())
	for c in cheques:
		c.days_left = date_diff(c.cheque_date, today)

	if filters.get("group_by_date"):
		columns, data = get_grouped(cheques)
	else:
		columns, data = get_detailed(cheques)

	return columns, data, None, get_chart(cheques), get_summary(cheques, today)


def get_detailed(cheques):
	columns = [
		{"label": _("Cheque Date"), "fieldname": "cheque_date", "fieldtype": "Date", "width": 110},
		{"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 90},
		{"label": _("Register ID"), "fieldname": "name", "fieldtype": "Link", "options": "Cheque Register", "width": 150},
		{"label": _("Cheque No"), "fieldname": "cheque_no", "fieldtype": "Data", "width": 110},
		{"label": _("Party"), "fieldname": "party_name", "fieldtype": "Data", "width": 200},
		{"label": _("Bank"), "fieldname": "cheque_bank", "fieldtype": "Data", "width": 130},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Cumulative"), "fieldname": "cumulative", "fieldtype": "Currency", "width": 130},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
	]
	running = 0
	for c in cheques:
		running += flt(c.amount)
		c.cumulative = running
	return columns, cheques


def get_grouped(cheques):
	columns = [
		{"label": _("Cheque Date"), "fieldname": "cheque_date", "fieldtype": "Date", "width": 120},
		{"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 90},
		{"label": _("Cheques"), "fieldname": "count", "fieldtype": "Int", "width": 90},
		{"label": _("Amount Needed in Bank"), "fieldname": "amount", "fieldtype": "Currency", "width": 170},
		{"label": _("Cumulative"), "fieldname": "cumulative", "fieldtype": "Currency", "width": 150},
	]
	by_date = {}
	for c in cheques:
		row = by_date.setdefault(
			c.cheque_date, {"cheque_date": c.cheque_date, "days_left": c.days_left, "count": 0, "amount": 0}
		)
		row["count"] += 1
		row["amount"] += flt(c.amount)

	running = 0
	data = []
	for key in sorted(by_date):
		row = by_date[key]
		running += row["amount"]
		row["cumulative"] = running
		data.append(row)
	return columns, data


def get_chart(cheques):
	totals = {}
	for c in cheques:
		totals[c.cheque_date] = totals.get(c.cheque_date, 0) + flt(c.amount)
	if not totals:
		return None
	dates = sorted(totals)
	return {
		"data": {
			"labels": [formatdate(d) for d in dates],
			"datasets": [{"name": _("Amount"), "values": [totals[d] for d in dates]}],
		},
		"type": "bar",
		"fieldtype": "Currency",
	}


def get_summary(cheques, today):
	week_end = add_days(today, 7)
	overdue = sum(flt(c.amount) for c in cheques if getdate(c.cheque_date) < today)
	due_today = sum(flt(c.amount) for c in cheques if getdate(c.cheque_date) == today)
	next_week = sum(flt(c.amount) for c in cheques if today <= getdate(c.cheque_date) <= week_end)
	total = sum(flt(c.amount) for c in cheques)
	return [
		{"value": overdue, "label": _("Overdue for Clearance"), "datatype": "Currency", "indicator": "Red"},
		{"value": due_today, "label": _("Due Today"), "datatype": "Currency", "indicator": "Orange"},
		{"value": next_week, "label": _("Next 7 Days (incl. today)"), "datatype": "Currency", "indicator": "Blue"},
		{"value": total, "label": _("Total Un-cleared"), "datatype": "Currency", "indicator": "Grey"},
	]
