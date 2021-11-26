# -*- coding: utf-8 -*-

import time
import math
import re

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    # nit_digifactfel = fields.Char('Nit DIGIFACTFEL')
    # feel_frase = fields.Char('Tipo de frase Feel')
    fel_frase_ids = fields.One2many('fel.frases','company_id','Frases')
    # feel_codigo_exportador = fields.Char('Codigo exportador')
    usuario_fel = fields.Char('Usuario fel')
    pass_fel = fields.Char('Contraseña fel')
    prueba_fel = fields.Boolean('Fel prueba')
    cliente_fel = fields.Integer('Id cliente')
    contrato_fel = fields.Integer('Id contrato')
    origen_fel = fields.Char('Id origen')
    # feel_codigo_exportador = fields.Char('Codigo exportador')
    # feel_logo = fields.Binary('Logo fel')
    # feel_texto_logo = fields.Char('Texto logo fel')
    # feel_codigo_establecimiento = fields.Char('Codigo de establecimiento')
