import frappe
from frappe.model.document import Document

class BankChequeLayout(Document):
	def validate(self):
		# একাধিক লেআউট যেন ডিফল্ট হিসেবে মার্ক না থাকে তা নিশ্চিত করা
		if self.is_default:
			frappe.db.sql(
				"UPDATE `tabBank Cheque Layout` SET is_default = 0 WHERE name != %s",
				(self.name,)
			)
