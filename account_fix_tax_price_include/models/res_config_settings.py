# -*- coding: utf-8 -*-
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import fields, models, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fix_tax_price_include = fields.Boolean(related='company_id.fix_tax_price_include', string='Fix Base Tax on price include?', readonly=False)