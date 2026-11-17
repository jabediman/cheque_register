frappe.ui.form.on("Cheque Settings", {
	setup(frm) {
		frm.set_query("cheques_in_hand_account", "company_defaults", function(doc, cdt, cdn) {
			const row = locals[cdt][cdn];
			return {
				filters: {
					company: row.company,
					is_group: 0
				}
			};
		});
		frm.set_query("cheques_issued_account", "company_defaults", function(doc, cdt, cdn) {
			const row = locals[cdt][cdn];
			return {
				filters: {
					company: row.company,
					is_group: 0
				}
			};
		});
	}
});
