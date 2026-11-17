// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.query_reports["Cheque Due Schedule"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "cheque_type",
			label: __("Cheque Type"),
			fieldtype: "Select",
			options: "Payment Cheque\nCollection Cheque",
			default: "Payment Cheque",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nIssued\nReceived\nDeposited\nCleared\nDishonoured\nCancelled",
			description: __("Leave empty to see only cheques that still need action"),
		},
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date" },
		{ fieldname: "group_by_date", label: __("Group by Date"), fieldtype: "Check", default: 0 },
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "days_left" && data && data.days_left !== undefined) {
			const d = data.days_left;
			if (d < 0) return `<span style="color: var(--red-600); font-weight: 600">${value}</span>`;
			if (d === 0) return `<span style="color: var(--orange-600); font-weight: 600">${value}</span>`;
			if (d <= 3) return `<span style="color: var(--yellow-700)">${value}</span>`;
		}
		return value;
	},
};
