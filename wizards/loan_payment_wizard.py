from odoo import models, fields

class LoanPaymentWizard(models.TransientModel):
    _name = 'loan.payment.wizard'
    _description = 'Wizard to register payments'

    loan_id = fields.Many2one('loan.loan', string='Loan', required=True, readonly=True)
    paid_amount = fields.Float(string="Paid Amount", required=True)
    payment_date = fields.Date(string="Payment Date", required=True, default=fields.Date.today)
    notes = fields.Text(string="Notes")

    def action_confirm_payment(self):
        self.ensure_one()

        self.loan_id.action_register_payment(
            paid_amount=self.paid_amount,
            payment_date=self.payment_date,
            notes=self.notes,
        )

        return {'type': 'ir.actions.act_window_close'}