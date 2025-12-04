from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo import _

class LoanLine(models.Model):
    _name = 'loan.line'
    _description = 'Payment History / Amortization'

    loan_id = fields.Many2one('loan.loan', string='Loan', required=True, ondelete='cascade', readonly=True)
    movement_date = fields.Date(string='Movement Date', required=True, readonly=True)
    paid_amount = fields.Float(string='Paid Amount', required=True, readonly=True)
    interest = fields.Float(string='Interest', readonly=True)
    feci = fields.Float(string='FECI', readonly=True)
    capital_payment = fields.Float(string='Capital Payment', readonly=True)
    principal_balance = fields.Float(string='Principal Balance', readonly=True)
    next_due_date = fields.Date(string='Next Due Date', readonly=True)
    notes = fields.Text(string='Notes')
    other_charge_ids = fields.Many2many('loan.other.charge', string='Applied Other Charges', readonly=True)

    @api.constrains('paid_amount')
    def _check_paid_amount(self):
        for line in self:
            if line.paid_amount is None or line.paid_amount <= 0:
                raise ValidationError(_("Paid amount must be greater than zero."))

    @api.constrains('movement_date')
    def _check_movement_date(self):
        for line in self:
            if line.loan_id and line.movement_date < line.loan_id.disbursement_date:
                raise ValidationError(_("Cannot register a payment before the disbursement date."))
            
    def unlink(self):
        for line in self:
            if line.other_charge_ids:
                raise ValidationError(
                    _("This payment line cannot be deleted because it has associated charges. "
                      "Please remove the charges first.")
                )
        return super(LoanLine, self).unlink()