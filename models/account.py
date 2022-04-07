# -*- coding: utf-8 -*-

import time
import math
import re

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import logging

class AccountJournal(models.Model):
    _inherit = "account.journal"

    tipo_dte_fel = fields.Selection([
            ('FACT', 'Factura'),
            ('FCAM', 'Factura cambiaria'),
            ('FPEQ', 'Factura pequeño contribuyente'),
            ('FCAP', 'Factura cambiaria pequeño contribuyente'),
            ('FESP', 'Factura especial'),
            ('NABN','Nota de abono'),
            ('RDON','Recibo de donación'),
            ('RECI','Recibo'),
            ('NDEB','Nota de Débito'),
            ('NCRE','Nota de Crédito'),
            ('FACA','Factura Contribuyente Agropecuario'),
            ('FCCA','Factura Cambiaria Contribuyente Agropecuario'),
            ('FAPE','Factura Pequeño contribuyente Regimen Elctrónico'),
            ('FCPE','Factura Cambiaria Pequeño contribuyente Regimen Elctrónico'),
            ('FAAE','Factura Contribuyente Agropecuario Régimen Electrónico especial'),
            ('FCAE','Factura Cambiaria Contribuyente Agropecuario Régimen Electrónico especial'),
        ],string="Tipo DTE",
        help="Tipo de DTE (documento para feel)")

    codigo_establecimiento_fel = fields.Char('Codigo de establecimiento')
    # feel_usuario = fields.Char('Usuario feel')
    # feel_llave_pre_firma = fields.Char('Llave pre firma feel')
    # feel_llave_firma = fields.Char('Llave firma feel')
    nombre_comercial_fel = fields.Char('Nombre comercial')
    producto_descripcion = fields.Boolean('Producto + descripcion')
    descripcion_factura = fields.Boolean('Descripcion factura')
    direccion_sucursal = fields.Char('Dirección')
    telefono = fields.Char('Teléfono')
    codigo_postal = fields.Char('Codigo postal')


class AccountTax(models.Model):
    _inherit = 'account.tax'



    @api.multi
    def compute_all(self, price_unit, currency=None, quantity=1.0, product=None, partner=None):
        """ Returns all information required to apply taxes (in self + their children in case of a tax group).
            We consider the sequence of the parent for group of taxes.
                Eg. considering letters as taxes and alphabetic order as sequence :
                [G, B([A, D, F]), E, C] will be computed as [A, D, F, C, E, G]

        RETURN: {
            'total_excluded': 0.0,    # Total without taxes
            'total_included': 0.0,    # Total with taxes
            'taxes': [{               # One dict for each tax in self and their children
                'id': int,
                'name': str,
                'amount': float,
                'sequence': int,
                'account_id': int,
                'refund_account_id': int,
                'analytic': boolean,
            }]
        } """
        if len(self) == 0:
            company_id = self.env.user.company_id
        else:
            company_id = self[0].company_id
        if not currency:
            currency = company_id.currency_id
        taxes = []
        # By default, for each tax, tax amount will first be computed
        # and rounded at the 'Account' decimal precision for each
        # PO/SO/invoice line and then these rounded amounts will be
        # summed, leading to the total amount for that tax. But, if the
        # company has tax_calculation_rounding_method = round_globally,
        # we still follow the same method, but we use a much larger
        # precision when we round the tax amount for each line (we use
        # the 'Account' decimal precision + 5), and that way it's like
        # rounding after the sum of the tax amounts of each line
        prec = currency.decimal_places
        prec = 5
        logging.warning('PRESICION DECIMAL')
        logging.warning(prec)

        # In some cases, it is necessary to force/prevent the rounding of the tax and the total
        # amounts. For example, in SO/PO line, we don't want to round the price unit at the
        # precision of the currency.
        # The context key 'round' allows to force the standard behavior.
        round_tax = False if company_id.tax_calculation_rounding_method == 'round_globally' else True
        round_total = True
        if 'round' in self.env.context:
            round_tax = bool(self.env.context['round'])
            round_total = bool(self.env.context['round'])

        if not round_tax:
            prec += 5

        base_values = self.env.context.get('base_values')
        if not base_values:
            total_excluded = total_included = base = round(price_unit * quantity, prec)
            logging.warning('EL BASE')
            logging.warning(base)
        else:
            total_excluded, total_included, base = base_values

        # Sorting key is mandatory in this case. When no key is provided, sorted() will perform a
        # search. However, the search method is overridden in account.tax in order to add a domain
        # depending on the context. This domain might filter out some taxes from self, e.g. in the
        # case of group taxes.
        for tax in self.sorted(key=lambda r: r.sequence):
            # Allow forcing price_include/include_base_amount through the context for the reconciliation widget.
            # See task 24014.
            if self._context.get('handle_price_include', True):
                price_include = self._context.get('force_price_include', tax.price_include)
            else:
                price_include = False

            if tax.amount_type == 'group':
                children = tax.children_tax_ids.with_context(base_values=(total_excluded, total_included, base))
                ret = children.compute_all(price_unit, currency, quantity, product, partner)
                total_excluded = ret['total_excluded']
                base = ret['base'] if tax.include_base_amount else base
                total_included = ret['total_included']
                tax_amount = total_included - total_excluded
                taxes += ret['taxes']
                continue

            tax_amount = tax._compute_amount(base, price_unit, quantity, product, partner)
            if not round_tax:
                tax_amount = round(tax_amount, prec)
                logging.warning('TAX AMONUT ROUND')
                logging.warning(tax_amount)
            else:
                tax_amount = currency.round(tax_amount)

            if price_include:
                total_excluded -= tax_amount
                base -= tax_amount
            else:
                total_included += tax_amount

            # Keep base amount used for the current tax
            tax_base = base

            if tax.include_base_amount:
                base += tax_amount

            taxes.append({
                'id': tax.id,
                'name': tax.with_context(**{'lang': partner.lang} if partner else {}).name,
                'amount': tax_amount,
                'base': tax_base,
                'sequence': tax.sequence,
                'account_id': tax.account_id.id,
                'refund_account_id': tax.refund_account_id.id,
                'analytic': tax.analytic,
                'price_include': tax.price_include,
                'tax_exigibility': tax.tax_exigibility,
            })

        return {
            'taxes': sorted(taxes, key=lambda k: k['sequence']),
            'total_excluded': currency.round(total_excluded) if round_total else total_excluded,
            'total_included': currency.round(total_included) if round_total else total_included,
            'base': base,
        }
