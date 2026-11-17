
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

// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

// Calls a whitelisted method on the Cheque Register controller, then reloads the form
function run_action(frm, method, args) {
	return frm
		.call({ doc: frm.doc, method: method, args: args || {}, freeze: true })
		.then(() => frm.reload_doc());
}

// Creates the Payment Entry from the cheque + invoice allocation, then opens it
function post_payment_entry(frm, submit) {
	const unallocated = flt(frm.doc.unallocated_amount);
	let message = submit
		? __("Create and submit the Payment Entry for this cheque?")
		: __("Create a draft Payment Entry for this cheque?");
	if (unallocated > 0) {
		message +=
			"<br><br>" +
			__("{0} is not allocated to any invoice and will be recorded as an advance on the party's account.", [
				format_currency(unallocated),
			]);
	}
	frappe.confirm(message, () => {
		frm.call({ doc: frm.doc, method: "make_payment_entry", args: { submit: submit }, freeze: true }).then((r) => {
			frm.reload_doc();
			if (r.message) frappe.show_alert({ message: __("Payment Entry {0} created", [r.message]), indicator: "green" });
		});
	});
}

frappe.ui.form.on("Cheque Register Invoice", {
	references_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "reference_doctype", frm.doc.party_type === "Customer" ? "Sales Invoice" : "Purchase Invoice");
	},

	reference_name(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.reference_name) return;
		frappe.db
			.get_value(row.reference_doctype, row.reference_name, ["posting_date", "grand_total", "outstanding_amount"])
			.then((r) => {
				const v = r.message || {};
				frappe.model.set_value(cdt, cdn, {
					posting_date: v.posting_date,
					invoice_total: v.grand_total,
					outstanding_amount: v.outstanding_amount,
					allocated_amount: Math.min(flt(v.outstanding_amount), flt(frm.doc.unallocated_amount)),
				});
			});
	},

	allocated_amount(frm) {
		frm.trigger("update_totals");
	},

	references_remove(frm) {
		frm.trigger("update_totals");
	},
});

frappe.ui.form.on("Cheque Register", {
	setup(frm) {
		const account_query = (filters) => () => ({
			filters: Object.assign({ company: frm.doc.company, is_group: 0 }, filters),
		});
		frm.set_query("cheque_in_hand_account", account_query({ root_type: "Asset" }));
		frm.set_query("under_collection_account", account_query({ root_type: "Asset" }));
		frm.set_query("pdc_payable_account", account_query({ root_type: "Liability" }));
		frm.set_query("bank_account", account_query({ account_type: ["in", ["Bank", "Cash"]] }));
		frm.set_query("bank_charges_account", account_query({ root_type: "Expense" }));
		frm.set_query("reference_name", "references", (doc) => ({
			filters: Object.assign(
				{ company: doc.company, docstatus: 1, outstanding_amount: [">", 0] },
				doc.party_type === "Customer" ? { customer: doc.party } : { supplier: doc.party }
			),
		}));
		frm.set_query("payment_entry", () => ({
			filters: {
				company: frm.doc.company,
				party: frm.doc.party,
				docstatus: ["<", 2],
				payment_type: frm.doc.cheque_type === "Collection Cheque" ? "Receive" : "Pay",
			},
		}));
	},

	onload(frm) {
		if (frm.is_new()) {
			if (!frm.doc.company) {
				frm.set_value("company", frappe.defaults.get_user_default("Company"));
			}
			frm.trigger("set_party_type");
		}
	},

	cheque_type(frm) {
		frm.trigger("set_party_type");
	},

	set_party_type(frm) {
		const type = frm.doc.cheque_type === "Collection Cheque" ? "Customer" : "Supplier";
		if (frm.doc.party_type !== type) {
			frm.set_value("party_type", type);
			frm.set_value("party", "");
		}
	},

	amount(frm) {
		frm.trigger("update_totals");
	},

	update_totals(frm) {
		const total = (frm.doc.references || []).reduce((s, r) => s + flt(r.allocated_amount), 0);
		frm.set_value("total_allocated", total);
		frm.set_value("unallocated_amount", flt(frm.doc.amount) - total);
	},

	refresh(frm) {
		frm.trigger("set_indicator");

		const incoming = frm.doc.cheque_type === "Collection Cheque";
		const status = frm.doc.status;
		const group = __("Actions");
		const open_status = !status || ["Received", "Issued"].includes(status);

		// allocation table is locked once the Payment Entry exists
		frm.set_df_property("references", "read_only", frm.doc.payment_entry ? 1 : 0);

		if (open_status && !frm.doc.payment_entry) {
			frm.add_custom_button(__("Get Outstanding Invoices"), () => frm.trigger("get_outstanding_invoices"));
		}

		if (frm.is_new() || frm.doc.docstatus !== 1) return;

		if (["Received", "Issued"].includes(status)) {
			if (!frm.doc.payment_entry) {
				frm.add_custom_button(__("Payment Entry (Submit)"), () => post_payment_entry(frm, 1), __("Create"));
				frm.add_custom_button(__("Payment Entry (Draft)"), () => post_payment_entry(frm, 0), __("Create"));
			}
			frm.add_custom_button(__("Cancel Cheque"), () => frm.trigger("cancel_cheque"), group);
		}

		if (incoming && status === "Received") {
			if (false) frm.add_custom_button(__("Deposit to Bank"), () => frm.trigger("deposit"), group);
			frm.page.set_inner_btn_group_as_primary(group);
		}
		if (incoming && status === "Deposited") {
			frm.add_custom_button(__("Cheque Passed"), () => frm.trigger("clear"), group);
			frm.add_custom_button(__("Cheque Bounced"), () => frm.trigger("dishonour"), group);
			frm.page.set_inner_btn_group_as_primary(group);
		}
		if (!incoming && status === "Issued") {
			frm.add_custom_button(__("Cheque Passed"), () => frm.trigger("clear"), group);
		}
	},

	set_indicator(frm) {
		const colors = {
			Received: "blue",
			Deposited: "orange",
			Cleared: "green",
			Dishonoured: "red",
			Issued: "blue",
			Cancelled: "gray",
		};
		if (frm.doc.status) {
			frm.page.set_indicator(__(frm.doc.status), colors[frm.doc.status]);
		}
	},

	// ---------- actions ----------
	get_outstanding_invoices(frm) {
		if (!(frm.doc.company && frm.doc.party && flt(frm.doc.amount) > 0)) {
			frappe.msgprint(__("Select Company, Party and enter the cheque Amount first."));
			return;
		}
		frm.call({ doc: frm.doc, method: "get_outstanding_invoices", freeze: true }).then((r) => {
			const rows = r.message || [];
			if (!rows.length) {
				frappe.msgprint(__("No outstanding invoices found for {0}.", [frm.doc.party]));
				return;
			}
			frm.clear_table("references");
			rows.forEach((d) => {
				// keep only invoices that receive some allocation; the user can add more manually
				if (flt(d.allocated_amount) > 0) frm.add_child("references", d);
			});
			frm.refresh_field("references");
			frm.trigger("update_totals");
		});
	},

	deposit(frm) {
		frappe.prompt(
			[{ fieldname: "deposit_date", fieldtype: "Date", label: __("Deposit Date"), default: frappe.datetime.get_today(), reqd: 1 }],
			(v) => run_action(frm, "mark_deposited", v),
			__("Deposit Cheque"),
			__("Deposit")
		);
	},

	clear(frm) {
		frappe.prompt(
			[{ fieldname: "clearance_date", fieldtype: "Date", label: __("Clearance Date"), default: frappe.datetime.get_today(), reqd: 1 }],
			(v) => run_action(frm, "mark_cleared", v),
			__("Cheque Cleared"),
			__("Confirm")
		);
	},

	dishonour(frm) {
		frappe.prompt(
			[
				{ fieldname: "dishonour_date", fieldtype: "Date", label: __("Dishonour Date"), default: frappe.datetime.get_today(), reqd: 1 },
				{
					fieldname: "reason",
					fieldtype: "Select",
					label: __("Reason"),
					reqd: 1,
					options: [
						"Funds Insufficient",
						"Payment Stopped by Drawer",
						"Signature Differs",
						"Account Closed",
						"Amount in Words and Figures Differ",
						"Stale / Post-dated",
						"Other",
					].join("\n"),
				},
				{ fieldname: "bank_charges", fieldtype: "Currency", label: __("Bank Charges") },
				{
					fieldname: "bank_charges_account",
					fieldtype: "Link",
					options: "Account",
					label: __("Bank Charges Account"),
					depends_on: "eval:doc.bank_charges > 0",
					mandatory_depends_on: "eval:doc.bank_charges > 0",
					get_query: () => ({ filters: { company: frm.doc.company, root_type: "Expense", is_group: 0 } }),
				},
				{
					fieldname: "cancel_payment_entry",
					fieldtype: "Check",
					label: __("Cancel Payment Entry (re-open invoices)"),
					default: 1,
					hidden: frm.doc.payment_entry ? 0 : 1,
				},
			],
			(v) => run_action(frm, "mark_dishonoured", v),
			__("Cheque Dishonoured"),
			__("Dishonour")
		);
	},

	cancel_cheque(frm) {
		frappe.confirm(__("Mark this cheque as Cancelled?"), () => run_action(frm, "mark_cancelled"));
	},
});


function update_bank_account_filter(frm) {
	if (!frm.doc.company) return;

	// Payment Cheque হলে এবং Cheque Bank সিলেক্ট করা থাকলে শুধু ওই ব্যাংকের অ্যাকাউন্টগুলো ফিল্টার করা
	if (frm.doc.cheque_type === "Payment Cheque" && frm.doc.cheque_bank) {
		frappe.call({
			method: "cheque_register.cheque_register.doctype.cheque_register.cheque_register.get_gl_accounts_for_bank",
			args: {
				company: frm.doc.company,
				bank: frm.doc.cheque_bank
			},
			callback(r) {
				const acc_list = r.message || [];
				frm.set_query("bank_account", () => {
					if (acc_list.length > 0) {
						return {
							filters: {
								name: ["in", acc_list],
								company: frm.doc.company,
								is_group: 0
							}
						};
					}
					return {
						filters: {
							company: frm.doc.company,
							account_type: ["in", ["Bank", "Cash"]],
							is_group: 0
						}
					};
				});

				// যদি ওই ব্যাংকের ১টি মাত্র অ্যাকাউন্ট থাকে তবে অটো সিলেক্ট করে দেওয়া
				if (acc_list.length === 1) {
					frm.set_value("bank_account", acc_list[0]);
				} else if (acc_list.length > 1 && frm.doc.bank_account && !acc_list.includes(frm.doc.bank_account)) {
					frm.set_value("bank_account", "");
				}
			}
		});
	} else {
		// Collection Cheque হলে কোম্পানির যেকোনো Bank বা Cash অ্যাকাউন্ট দেখাবে
		frm.set_query("bank_account", () => {
			return {
				filters: {
					company: frm.doc.company,
					account_type: ["in", ["Bank", "Cash"]],
					is_group: 0
				}
			};
		});
	}
}

frappe.ui.form.on("Cheque Register", {
	refresh(frm) {
		const hide_list = [
			"mode_of_payment",
			"cheques_in_hand_account",
			"cheque_in_hand_account",
			"cheques_issued_account",
			"pdc_payable_account",
			"under_collection_account"
		];
		hide_list.forEach(fn => {
			if (frm.fields_dict[fn]) {
				frm.set_df_property(fn, "hidden", 1);
			}
		});
		update_bank_account_filter(frm);
	},
	cheque_type(frm) {
		update_bank_account_filter(frm);
	},
	cheque_bank(frm) {
		update_bank_account_filter(frm);
	},
	company(frm) {
		update_bank_account_filter(frm);
	}
});


frappe.ui.form.on("Cheque Register", {
    onload: function(frm) {
        if (frm.is_new() && frm.doc.company) {
            frm.trigger("fetch_company_cheque_defaults");
        }
    },
    company: function(frm) {
        frm.trigger("fetch_company_cheque_defaults");
    },
    fetch_company_cheque_defaults: function(frm) {
        if (!frm.doc.company) return;
        frappe.db.get_doc("Cheque Settings").then(settings => {
            if (!settings) return;
            let row = null;
            for (let key of Object.keys(settings)) {
                if (Array.isArray(settings[key])) {
                    row = settings[key].find(r => r.company === frm.doc.company);
                    if (row) break;
                }
            }
            const src = row || settings;
            if (src.default_mode_of_payment && !frm.doc.mode_of_payment) {
                frm.set_value("mode_of_payment", src.default_mode_of_payment);
            }
            const in_hand = src.cheques_in_hand_account || src.cheque_in_hand_account;
            if (in_hand) {
                frm.set_value("cheque_in_hand_account", in_hand);
            }
            const issued = src.cheques_issued_account || src.pdc_payable_account;
            if (issued) {
                frm.set_value("pdc_payable_account", issued);
            }
        });
    }
});


frappe.ui.form.on("Cheque Register", {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.cheque_type === "Collection Cheque" && frm.doc.status === "Received") {
            frm.add_custom_button(__("Cheque Passed"), function() {
                frappe.prompt(
                    [{ fieldname: "clearance_date", fieldtype: "Date", label: __("Clearance Date"), default: frappe.datetime.get_today(), reqd: 1 }],
                    function(values) {
                        frm.call({
                            method: "mark_cleared",
                            doc: frm.doc,
                            args: { clearance_date: values.clearance_date },
                            freeze: true,
                            callback: function() { frm.reload_doc(); }
                        });
                    },
                    __("Mark Cheque Passed"),
                    __("Confirm")
                );
            }, __("Actions"));
        }
    }
});
