# -*- coding: utf-8 -*-

import time
import math
import re

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _
import requests
import logging
import base64
from lxml import etree
import xml.etree.ElementTree as ET
import datetime

class FelFrases(models.Model):
    _name = "fel.frases"

    company_id = fields.Many2one('res.company')
    codigo = fields.Char('Codigo')
    frase = fields.Char('Frase')
