# -*- coding: utf-8 -*-

import time
import math
import re

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = "res.partner"

    documento_personal_identificacion = fields.Char('DPI')
    pasaporte = fields.Char('Pasaporte')
    codigo_comprador = fields.Char('Codigo comprador')

    # feel_codigo_establecimiento = fields.Char('Codigo de establecimiento')
