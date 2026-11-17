import frappe

BD_BANKS = [
    "AB Bank PLC", "Agrani Bank PLC", "Al-Arafah Islami Bank PLC",
    "Bangladesh Commerce Bank Limited", "Bangladesh Development Bank PLC",
    "Bangladesh Krishi Bank", "Bank Al-Falah Limited", "Bank Asia PLC",
    "BASIC Bank Limited", "Bengal Commercial Bank PLC", "BRAC Bank PLC",
    "Citibank N.A.", "Citizens Bank PLC", "City Bank PLC",
    "Commercial Bank of Ceylon PLC", "Community Bank Bangladesh PLC",
    "Dhaka Bank PLC", "Dhaka Mercantile Co-operative Bank Limited",
    "Dutch-Bangla Bank PLC", "Eastern Bank PLC", "EXIM Bank PLC",
    "First Security Islami Bank PLC", "Global Islami Bank PLC",
    "Habib Bank Limited", "HSBC Bangladesh", "ICB Islamic Bank Limited",
    "IFIC Bank PLC", "Islami Bank Bangladesh PLC", "Jamuna Bank PLC",
    "Janata Bank PLC", "Meghna Bank PLC", "Mercantile Bank PLC",
    "Midland Bank PLC", "Modhumoti Bank PLC", "Mutual Trust Bank PLC",
    "National Bank Limited", "National Bank of Pakistan",
    "National Credit & Commerce Bank PLC (NCC Bank)", "NRB Bank PLC",
    "NRBC Bank PLC", "One Bank PLC", "Padma Bank PLC", "Prime Bank PLC",
    "Pubali Bank PLC", "Rajshahi Krishi Unnayan Bank (RAKUB)",
    "Rupali Bank PLC", "Shahjalal Islami Bank PLC", "Shimanto Bank PLC",
    "Social Islami Bank PLC", "Sonali Bank PLC",
    "South Bangla Agriculture & Commerce Bank PLC (SBAC)",
    "Southeast Bank PLC", "Standard Bank PLC", "Standard Chartered Bank",
    "State Bank of India", "Trust Bank PLC", "Union Bank PLC",
    "United Commercial Bank PLC (UCB)", "Uttara Bank PLC", "Woori Bank"
]

def setup_bd_banks():
    for bank_name in BD_BANKS:
        if not frappe.db.exists("Bank", bank_name):
            frappe.get_doc({"doctype": "Bank", "bank_name": bank_name}).insert(ignore_permissions=True)
        if frappe.db.exists("DocType", "Bank Cheque Layout") and not frappe.db.exists("Bank Cheque Layout", bank_name):
            frappe.get_doc({"doctype": "Bank Cheque Layout", "bank_name": bank_name, "is_default": 0}).insert(ignore_permissions=True)
    frappe.db.commit()
    print("Successfully inserted all Bangladeshi banks!")
