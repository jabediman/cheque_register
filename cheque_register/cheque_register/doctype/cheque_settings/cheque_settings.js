
function _get_company_cheque_row(settings_doc, company) {
    if (!settings_doc) return {};
    for (let key of Object.keys(settings_doc)) {
        if (Array.isArray(settings_doc[key])) {
            let match = settings_doc[key].find(r => r.company === company);
            if (match) return match;
        }
    }
    return settings_doc;
}

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
