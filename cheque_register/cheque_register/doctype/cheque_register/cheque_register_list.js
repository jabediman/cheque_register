frappe.listview_settings["Cheque Register"] = {
	add_fields: ["status", "cheque_type", "cheque_date"],
	get_indicator(doc) {
		const today = frappe.datetime.get_today();

		if (doc.status === "Received" && doc.cheque_date <= today) {
			return [__("Ready to Deposit"), "orange", "status,=,Received"];
		}
		if (doc.status === "Received") {
			return [__("Post-dated"), "blue", "status,=,Received"];
		}
		const map = {
			Deposited: ["orange", "status,=,Deposited"],
			Cleared: ["green", "status,=,Cleared"],
			Dishonoured: ["red", "status,=,Dishonoured"],
			Issued: ["blue", "status,=,Issued"],
			Cancelled: ["gray", "status,=,Cancelled"],
		};
		const m = map[doc.status];
		return m ? [__(doc.status), m[0], m[1]] : null;
	},
};
