from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from odoo import _

class LoanOtherCharge(models.Model):
    _name = 'loan.other.charge'
    _description = 'Loan Other Charges'

    loan_id = fields.Many2one('loan.loan', string='Loan', required=True, ondelete='cascade', readonly=True)
    description = fields.Char(string='Description', required=True)
    amount = fields.Float(string='Amount', required=True)
    amount_paid = fields.Float(string='Amount Paid', default=0, readonly=True)
    pending_balance = fields.Float(string='Pending Balance', compute='_compute_pending_balance', store=True)
    creation_date = fields.Date(string='Creation Date', default=fields.Date.today, readonly=True)
    due_date = fields.Date(string='Due Date')

    @api.constrains('amount', 'amount_paid')
    def _check_amounts(self):
        for charge in self:
            if charge.amount < 0:
                raise ValidationError(_("Charge amount cannot be negative."))

            if charge.amount_paid < 0:
                raise ValidationError(_("Amount paid cannot be negative."))

            if charge.amount_paid > charge.amount:
                raise ValidationError(_("Amount paid cannot exceed the total charge amount."))

    @api.depends('amount', 'amount_paid')
    def _compute_pending_balance(self):
        for charge in self:
            try:
                if charge.amount is None or charge.amount_paid is None:
                    charge.pending_balance = 0
                    continue

                balance = charge.amount - charge.amount_paid

                if balance < 0:
                    raise UserError(
                        _("Error calculating pending balance: amount paid (%s) exceeds total amount (%s).")
                        % (charge.amount_paid, charge.amount)
                    )

                charge.pending_balance = balance

            except ValidationError:
                raise
            except UserError:
                raise
            except Exception as e:
                raise UserError(_("Unexpected error calculating pending balance: %s") % str(e))