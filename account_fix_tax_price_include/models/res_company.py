# -*- coding: utf-8 -*-
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api
import logging
log = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = "res.company"

    fix_tax_price_include = fields.Boolean(string='Fix Base Tax on price include?')