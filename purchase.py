# This file is part of purchase_payment_type module for Tryton.  The COPYRIGHT
# file at the top level of this repository contains the full copyright notices
# and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

__all__ = ['PaymentType', 'Purchase']


_STATES = {
    'readonly': Eval('state') != 'draft',
}
_DEPENDS = ['state']
ZERO = Decimal('0.0')


class PaymentType(metaclass=PoolMeta):
    __name__ = 'account.payment.type'

    @classmethod
    def __setup__(cls):
        super(PaymentType, cls).__setup__()
        cls._check_modify_related_models.add(
            ('purchase.purchase', 'payment_type'))


class Purchase(metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    payment_type = fields.Many2One('account.payment.type',
        'Payment Type', states=_STATES, depends=_DEPENDS,
        domain=[('kind', 'in', ('payable', 'both'))])

    @classmethod
    def default_payment_type(cls):
        PaymentType = Pool().get('account.payment.type')
        payment_types = PaymentType.search(cls.payment_type.domain)
        if len(payment_types) == 1:
            return payment_types[0].id

    @fields.depends('party')
    def on_change_party(self):
        super(Purchase, self).on_change_party()
        self.payment_type = None
        if self.party and self.party.supplier_payment_type:
            self.payment_type = self.party.supplier_payment_type

    def _get_invoice_purchase(self):
        invoice = super(Purchase, self)._get_invoice_purchase()
        if self.payment_type:
            # set None payment type to control payable/receivable kind
            # depend untaxed amount
            invoice.payment_type = None
        return invoice

    def create_invoice(self):
        invoice = super(Purchase, self).create_invoice()

        if invoice:
            payment_type = self._get_invoice_payment_type(invoice)
            if payment_type:
                invoice.payment_type = payment_type
        return invoice

    def _get_invoice_payment_type(self, invoice):
        if self.payment_type and self.payment_type.kind == 'both':
            return self.payment_type

        # issue10801 invoice has not untaxed_amount and lines has not amount
        # because is pending to do save()
        if not hasattr(invoice, 'untaxed_amount'):
            invoice.untaxed_amount = sum((Decimal(str(line.quantity or '0.0'))
                    * (line.unit_price or Decimal('0.0')))
                for line in invoice.lines if line.type == 'line' )

        if invoice.untaxed_amount >= ZERO:
            kind = 'payable'
            name = 'supplier_payment_type'
        else:
            kind = 'receivable'
            name = 'customer_payment_type'

        if self.payment_type and self.payment_type.kind == kind:
            return self.payment_type
        else:
            payment_type = getattr(self.party, name)
            return payment_type if payment_type else None
