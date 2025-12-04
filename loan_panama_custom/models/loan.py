from odoo import models, fields, api
from odoo import _
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Optional, List, Tuple
from odoo.exceptions import UserError, ValidationError

class Loan(models.Model):
    _name = 'loan.loan'
    _description = 'General Info and Balance'
    
    name = fields.Char(string='Loan Reference', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    principal_amount = fields.Float(string='Principal Amount', required=True)
    current_balance = fields.Float(string='Current Balance', compute='_compute_current_balance')
    annual_interest_rate = fields.Float(string='Annual Interest Rate (%)', required=True, default=19.0)
    annual_feci_rate = fields.Float(string='Annual FECI Rate (%)', default=1.0)
    feci_threshold = fields.Float(string='FECI Threshold', default=5000.0, help='Minimum balance to apply FECI')
    disbursement_date = fields.Date(string='Disbursement Date', required=True)
    next_due_date = fields.Date(string='Next Due Date')
    credit_officer = fields.Char(string='Credit Officer')
    account = fields.Char(string='Account')
    income_source = fields.Char(string='Income Source(s)')
    term_months = fields.Integer(string='Term (months)')
    monthly_installment = fields.Float(string='Monthly Installment')
    collateral = fields.Char(string='Collateral')
    dealer = fields.Char(string='Dealer')
    notes = fields.Text(string='Notes')
    loan_type = fields.Selection(
        [
            ('individual', 'Individual'),
            ('corporate', 'Corporate'),
            ('personal', 'Personal'),
            ('auto', 'Auto'),
            ('mortgage', 'Mortgage'),
        ],
        string='Loan Type'
    )
    payment_frequency = fields.Selection([
        ('monthly', 'Monthly'),
        ('biweekly', 'Biweekly'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily'),
    ], string='Payment Frequency', default='monthly')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('defaulter', 'Defaulter'),
    ], string='Status', default='draft', compute="_compute_status")
    feci_exempt = fields.Boolean(
        string='FECI Exempt',
        default=False,
        help='Indicates if this loan is exempt from FECI calculation.'
    )
    loan_line_ids = fields.One2many('loan.line', 'loan_id', string='Payment Lines')
    other_charge_ids = fields.One2many('loan.other.charge', 'loan_id', string='Other Charges')

    @api.constrains('principal_amount')
    def _check_principal_amount(self):
        for loan in self:
            if loan.principal_amount is None or loan.principal_amount <= 0:
                raise ValidationError(_("Principal amount must be greater than zero."))

    @api.constrains('annual_interest_rate')
    def _check_annual_interest_rate(self):
        for loan in self:
            if loan.annual_interest_rate is None or loan.annual_interest_rate < 0:
                raise ValidationError(_("Annual interest rate cannot be negative."))
            if loan.annual_interest_rate > 200:
                raise ValidationError(_("Annual interest rate exceeds allowed limit (200%)."))

    @api.constrains('annual_feci_rate')
    def _check_annual_feci_rate(self):
        for loan in self:
            if loan.annual_feci_rate is not None and loan.annual_feci_rate < 0:
                raise ValidationError(_("FECI rate cannot be negative."))

    @api.constrains('feci_threshold')
    def _check_feci_threshold(self):
        for loan in self:
            if loan.feci_threshold is not None and loan.feci_threshold < 0:
                raise ValidationError(_("FECI threshold cannot be negative."))

    @api.constrains('next_due_date', 'disbursement_date')
    def _check_due_dates(self):
        for loan in self:
            if loan.next_due_date and loan.disbursement_date:
                if loan.next_due_date < loan.disbursement_date:
                    raise ValidationError(_("Next due date cannot be before the disbursement date."))

    @api.constrains('payment_frequency')
    def _check_payment_frequency(self):
        valid = ['monthly', 'biweekly', 'weekly', 'daily']
        for loan in self:
            if loan.payment_frequency not in valid:
                raise ValidationError(_("The selected payment frequency is not valid."))

    @api.constrains('current_balance')
    def _check_current_balance(self):
        for loan in self:
            if loan.current_balance < 0:
                raise ValidationError(_("Balance cannot be negative."))

    @api.depends('loan_line_ids.capital_payment')
    def _compute_current_balance(self):
        for loan in self:
            try:
                total_paid = sum((line.capital_payment or 0.0) for line in loan.loan_line_ids)
                loan.current_balance = loan.principal_amount - total_paid
            except Exception as e:
                raise UserError(_("Error calculating current balance: %s") % str(e))

    @api.depends('current_balance', 'next_due_date')
    def _compute_status(self):
        today = date.today()
        for loan in self:
            try:
                if loan.current_balance == 0:
                    loan.status = 'closed'
                elif loan.next_due_date and loan.next_due_date < today:
                    loan.status = 'defaulter'
                else:
                    loan.status = 'active'
            except Exception as e:
                raise UserError(_("Error calculating loan status: %s") % str(e))
                
    def action_loan_payment_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'loan.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_loan_id': self.id},
        }
    
    def action_register_payment(self, paid_amount: float, payment_date: Optional[date] = None, notes: str = '') -> None:
        self.ensure_one()

        try:
            payment_date = payment_date or date.today()

            if paid_amount is None:
                raise ValidationError(_("You must specify a payment amount."))

            if paid_amount <= 0:
                raise ValidationError(_("Payment amount must be greater than zero."))

            if payment_date < self.disbursement_date:
                raise ValidationError(_("Payment date cannot be before the disbursement date."))

            principal_balance = self._calculate_principal_balance()
            days_elapsed = self._calculate_days_since_last_payment(payment_date)

            remaining_amount = paid_amount
            applied_charge_ids, remaining_amount = self._apply_other_charges(remaining_amount)
            feci_payment, remaining_amount = self._calculate_feci(principal_balance, days_elapsed, remaining_amount)
            interest_payment, remaining_amount = self._calculate_interest(principal_balance, days_elapsed, remaining_amount)
            capital_payment = max(remaining_amount, 0)

            line = self._create_payment_line(
                payment_date=payment_date,
                paid_amount=paid_amount,
                capital_payment=capital_payment,
                feci_payment=feci_payment,
                interest_payment=interest_payment,
                principal_balance=principal_balance - capital_payment,
                other_charge_ids=applied_charge_ids,
                notes=notes
            )

            self._update_next_due_date(payment_date, line)
            self._compute_current_balance()
            self._compute_status()

        except ValidationError:
            raise
        except UserError:
            raise
        except Exception as e:
            raise UserError(_("An unexpected error occurred while registering the payment: %s") % str(e))

    def _calculate_principal_balance(self) -> float:
        try:
            return self.principal_amount - sum((line.capital_payment or 0.0) for line in self.loan_line_ids)
        except Exception as e:
            raise UserError(_("Error calculating principal balance: %s") % str(e))

    def _calculate_days_since_last_payment(self, payment_date: date) -> int:
        try:
            last_line = self.loan_line_ids.sorted(key=lambda l: l.movement_date, reverse=True)
            last_payment_date = last_line[0].movement_date if last_line else self.disbursement_date
            return max((payment_date - last_payment_date).days, 0)
        except Exception as e:
            raise UserError(_("Error calculating days since last payment: %s") % str(e))

    def _apply_other_charges(self, remaining_amount: float) -> Tuple[List[int], float]:
        try:
            applied_charges = []
            for charge in self.other_charge_ids.filtered(lambda c: c.pending_balance > 0):
                if remaining_amount <= 0:
                    break
                apply_amt = min(remaining_amount, charge.pending_balance)
                charge.amount_paid += apply_amt
                remaining_amount -= apply_amt
                applied_charges.append(charge.id)
            return applied_charges, remaining_amount
        except Exception as e:
            raise UserError(_("Error applying other charges: %s") % str(e))

    def _calculate_feci(self, principal_balance: float, days: int, remaining_amount: float) -> Tuple[float, float]:
        try:
            if principal_balance < self.feci_threshold or self.feci_exempt:
                return 0.0, remaining_amount

            base = principal_balance - self.feci_threshold
            total_feci = base * (self.annual_feci_rate / 100) * days / 365
            feci_payment = min(remaining_amount, total_feci)
            return feci_payment, remaining_amount - feci_payment
        except Exception as e:
            raise UserError(_("Error calculating FECI: %s") % str(e))

    def _calculate_interest(self, principal_balance: float, days: int, remaining_amount: float) -> Tuple[float, float]:
        try:
            total_interest = principal_balance * (self.annual_interest_rate / 100) * days / 365
            interest_payment = min(remaining_amount, total_interest)
            return interest_payment, remaining_amount - interest_payment
        except Exception as e:
            raise UserError(_("Error calculating interest: %s") % str(e))

    def _create_payment_line(self, payment_date, paid_amount, capital_payment, feci_payment, interest_payment, principal_balance, other_charge_ids, notes):
        try:
            return self.env['loan.line'].create({
                'loan_id': self.id,
                'movement_date': payment_date,
                'paid_amount': paid_amount,
                'interest': interest_payment,
                'feci': feci_payment,
                'capital_payment': capital_payment,
                'principal_balance': principal_balance,
                'other_charge_ids': [(6, 0, other_charge_ids)],
                'notes': notes,
            })
        except Exception as e:
            raise UserError(_("Error creating payment line: %s") % str(e))

    def _update_next_due_date(self, payment_date: date, line) -> None:
        try:
            delta_mapping = {
                'monthly': relativedelta(months=1),
                'biweekly': relativedelta(days=15),
                'weekly': relativedelta(weeks=1),
                'daily': relativedelta(days=1),
            }

            delta = delta_mapping.get(self.payment_frequency, relativedelta(months=1))

            line.next_due_date = payment_date + delta
        except Exception as e:
            raise UserError(_("Error updating next due date: %s") % str(e))