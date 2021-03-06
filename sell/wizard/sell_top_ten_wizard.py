# -*- coding: utf-8 -*-

from datetime import date, timedelta
from odoo import models, fields, api
from odoo.exceptions import UserError


class sell_top_ten_wizard(models.TransientModel):
    _name = 'sell.top.ten.wizard'
    _description = u'销量前十商品向导'

    @api.model
    def _default_date_start(self):
        '''返回6天前的日期'''
        now = date.today()
        return (now - timedelta(days=6)).strftime('%Y-%m-%d')

    @api.model
    def _default_date_end(self):
        return date.today()

    date_start = fields.Date(u'开始日期', default=_default_date_start,
                             help=u'报表汇总的开始日期，默认为一周前日期')
    date_end = fields.Date(u'结束日期', default=_default_date_end,
                           help=u'报表汇总的结束日期，默认为当前日期')
    warehouse_id = fields.Many2one('warehouse', u'仓库',
                                   help=u'按指定仓库进行统计')

    @api.multi
    def button_ok(self):
        self.ensure_one()
        if self.date_end < self.date_start:
            raise UserError(u'开始日期不能大于结束日期！')

        return {
            'name': u'销量前十商品',
            'view_mode': 'tree',
            'res_model': 'sell.top.ten',
            'type': 'ir.actions.act_window',
            'context': self.read(['date_start', 'date_end', 'warehouse_id'])[0],
        }
