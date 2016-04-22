# -*- coding: utf-8 -*-

from openerp import models, fields, api
from openerp.exceptions import except_orm
from datetime import datetime

ISODATEFORMAT = '%Y-%m-%d'
ISODATETIMEFORMAT = "%Y-%m-%d %H:%M:%S"


class TrialBalance(models.Model):
    _name = "trial.balance"

    period_id = fields.Many2one('finance.period', string='会计期间')
    subject_code = fields.Char(u'科目编码')
    subject_name_id = fields.Many2one('finance.account', string='科目名称')
    initial_balance_debit = fields.Float(u'期初余额', child_string=" 借方")
    initial_balance_credit = fields.Float(u'期初余额(贷方)', child_string="贷方")
    current_occurrence_debit = fields.Float(u'本期发生额', child_string="借方")
    current_occurrence_credit = fields.Float(u'本期发生额(贷方)', child_string="贷方")
    ending_balance_debit = fields.Float(u'期末余额', child_string="借方")
    ending_balance_credit = fields.Float(u'期末余额(贷方)', child_string="贷方")
    cumulative_occurrence_debit = fields.Float(u'本年累计发生额', child_string="借方")
    cumulative_occurrence_credit = fields.Float(u'本年累计发生额(贷方)', child_string="贷方")


class CreateTrialBalanceWizard(models.TransientModel):
    _name = "create.trial.balance.wizard"
    period_id = fields.Many2one('finance.period', string='会计期间')

    @api.multi
    def compute_last_period_id(self, period_id):
        if period_id.month == 1:
            year = int(period_id.year) - 1
            month = 12
        else:
            year = period_id.year
            month = int(period_id.month) - 1
        print year, month
        return self.env['finance.period'].search([('year', '=', year), ('month', '=', month)])

    @api.multi
    def compute_next_period_id(self, period_id):
        if period_id.month == 12:
            year = int(period_id.year) + 1
            month = 1
        else:
            year = period_id.year
            month = int(period_id.month) + 1
        print year, month
        return self.env['finance.period'].search([('year', '=', year), ('month', '=', month)])

    @api.multi
    def get_period_balance(self, period_id):
        """取出本期发生额
            返回结果是 科目 借 贷
         """
        sql = ''' select vol.account_id as account_id,sum(vol.debit) as debit,  sum(vol.credit) as credit  from voucher as vo left join voucher_line as vol
            on vo.id = vol.voucher_id where vo.period_id=%s
                 group by vol.account_id'''
        self.env.cr.execute(sql, (period_id,))
        return self.env.cr.dictfetchall()

    @api.multi
    def create_trial_balance(self):
        """ \
            生成科目余额表 \
            1.如果所选区间已经关闭则直接调出已有的科目余额表记录
            2.判断如果所选的区间的 前一个期间没有关闭则报错
            3.如果上一个区间不存在则报错

        """
        trial_balance_objs = self.env['trial.balance'].search([('period_id', '=', self.period_id.id)])
        trial_balance_ids = [balance.id for balance in trial_balance_objs]
        if not self.period_id.is_closed:
            trial_balance_objs.unlink()
            last_period = self.compute_last_period_id(self.period_id)
            if not last_period:
                raise except_orm(u'错误', u'上一个期间不存在,无法取到期初余额')
            if not last_period.is_closed:
                raise except_orm(u'错误', u'前一期间未结账，无法取到期初余额')
            period_id = self.period_id.id
            current_occurrence_dic_list = self.get_period_balance(period_id)
            trial_balance_dict = {}
            """把本期发生额的数量填写到  准备好的dict 中 """
            for current_occurrence in current_occurrence_dic_list:
                account = self.env['finance.account'].browse(current_occurrence.get('account_id'))

                account_dict = {'period_id': period_id, 'current_occurrence_debit': current_occurrence.get('debit'),
                                'current_occurrence_credit': current_occurrence.get('credit'), 'subject_code': account.code,
                                'initial_balance_credit': 0, 'initial_balance_debit': 0,
                                'ending_balance_credit': current_occurrence.get('credit'), 'ending_balance_debit': current_occurrence.get('debit'),
                                'cumulative_occurrence_credit': current_occurrence.get('credit'), 'cumulative_occurrence_debit': current_occurrence.get('debit'),
                                'subject_name_id': current_occurrence.get('account_id')}
                trial_balance_dict[current_occurrence.get('account_id')] = account_dict
            """ 结合上一期间的 数据 填写  trial_balance_dict(余额表 记录生成dict)   """
            for trial_balance in self.env['trial.balance'].search([('period_id', '=', last_period.id)]):
                initial_balance_credit = trial_balance.ending_balance_credit
                initial_balance_debit = trial_balance.ending_balance_debit
                subject_name_id = trial_balance.subject_name_id.id
                if subject_name_id in trial_balance_dict:
                    ending_balance_credit = trial_balance_dict[subject_name_id].get('current_occurrence_credit') + initial_balance_credit
                    ending_balance_debit = trial_balance_dict[subject_name_id].get('current_occurrence_debit') + initial_balance_debit
                    cumulative_occurrence_credit = trial_balance_dict[subject_name_id].get('current_occurrence_credit') + trial_balance.cumulative_occurrence_credit
                    cumulative_occurrence_debit = trial_balance_dict[subject_name_id].get('current_occurrence_debit') + trial_balance.cumulative_occurrence_debit
                else:
                    ending_balance_credit = initial_balance_credit
                    ending_balance_debit = initial_balance_debit
                    cumulative_occurrence_credit = trial_balance.cumulative_occurrence_credit
                    cumulative_occurrence_debit = trial_balance.cumulative_occurrence_debit

                subject_code = trial_balance.subject_code
                trial_balance_dict[subject_name_id] = {
                    'initial_balance_credit': initial_balance_credit,
                    'initial_balance_debit': initial_balance_debit,
                    'ending_balance_credit': ending_balance_credit,
                    'ending_balance_debit': ending_balance_debit,
                    'cumulative_occurrence_credit': cumulative_occurrence_credit,
                    'cumulative_occurrence_debit': cumulative_occurrence_debit,
                    'subject_code': subject_code,
                    'period_id': period_id,
                    'subject_name_id': subject_name_id
                }
            trial_balance_ids = [self.env['trial.balance'].create(vals).id for (key, vals) in trial_balance_dict.items()]
        view_id = self.env.ref('finance.trial_balance_tree').id
        return {
            'type': 'ir.actions.act_window',
            'name': '期末余额表',
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'trial.balance',
            'target': 'current',
            'view_id': False,
            'views': [(view_id, 'tree')],
            'domain': [('id', 'in', trial_balance_ids)]
        }


class CreateVouchersSummaryWizard(models.TransientModel):
    _name = "create.vouchers.summary.wizard"
    period_begin_id = fields.Many2one('finance.period', string='开始期间')
    period_end_id = fields.Many2one('finance.period', string='结束期间')
    subject_name_id = fields.Many2one('finance.account', string='科目名称')

    @api.multi
    def get_last_period_vouchers_summary(self, period):

        return period

    @api.multi
    def get_initial_balance(self, period, subject_name):
        vals_dict = {}
        trial_balance_obj = self.env['trial.balance'].search([('period_id', '=', period.id), ('subject_name_id', '=', subject_name)])
        if trial_balance_obj:
            initial_balance_credit = trial_balance_obj.ending_balance_credit
            initial_balance_debit = trial_balance_obj.ending_balance_debit
        else:
            initial_balance_credit = 0
            initial_balance_debit = 0
        now_period = self.env['create.trial.balance.wizard'].compute_next_period_id(period)
        print "+++++", period, "--------"
        direction_tuple = self.judgment_lending(initial_balance_credit, initial_balance_debit)
        vals_dict.update({
            'date': '%s-%s-01' % (now_period.year, now_period.month),
            'direction': direction_tuple[0],
            'balance': direction_tuple[1],
            'summary': u'期初余额'})
        return vals_dict

    @api.multi
    def judgment_lending(self, balance_credit, balance_debit):

        if balance_credit > balance_debit:
            direction = '贷'
            balance = balance_credit - balance_debit
        elif balance_credit < balance_debit:
            direction = '借'
            balance = balance_debit - balance_credit
        else:
            direction = '平'
            balance = 0
        return (direction, balance)

    @api.multi
    def get_ending_balance(self, period, subject_name):
        vals_dict = {}
        trial_balance_obj = self.env['trial.balance'].search([('period_id', '=', period.id), ('subject_name_id', '=', subject_name)])
        if trial_balance_obj:
            ending_balance_credit = trial_balance_obj.ending_balance_credit
            ending_balance_debit = trial_balance_obj.ending_balance_debit
        else:
            ending_balance_credit = 0
            ending_balance_debit = 0

        direction_tuple = self.judgment_lending(ending_balance_credit, ending_balance_debit)
        vals_dict.update({
            'date': '%s-%s-01' % (period.year, period.month),
            'direction': direction_tuple[0],
            'balance': direction_tuple[1],
            'debit': ending_balance_debit,
            'credit': ending_balance_credit,
            'summary': u'期末余额'})
        return vals_dict

    @api.multi
    def get_year_balance(self, period, subject_name):
        vals_dict = {}
        trial_balance_obj = self.env['trial.balance'].search([('period_id', '=', period.id), ('subject_name_id', '=', subject_name.id)])
        if trial_balance_obj:
            cumulative_occurrence_credit = trial_balance_obj.cumulative_occurrence_credit
            cumulative_occurrence_debit = trial_balance_obj.cumulative_occurrence_debit
        else:
            cumulative_occurrence_credit = 0
            cumulative_occurrence_debit = 0

        direction_tuple = self.judgment_lending(cumulative_occurrence_credit, cumulative_occurrence_debit)
        vals_dict.update({
            'date': '%s-%s-01' % (period.year, period.month),
            'direction': direction_tuple[0],
            'balance': direction_tuple[1],
            'debit': cumulative_occurrence_debit,
            'credit': cumulative_occurrence_credit,
            'summary': u'本年累计发生额'})
        return vals_dict

    @api.multi
    def get_current_occurrence_amount(self, period, subject_name):
        sql = ''' select vo.date as date, vo.id as voucher_id,COALESCE(vol.debit,0) as debit,vol.name as summary,COALESCE(vol.credit,0) as credit
         from voucher as vo left join voucher_line as vol
            on vo.id = vol.voucher_id where vo.period_id=%s and  vol.account_id=%s
                 '''
        self.env.cr.execute(sql, (period.id, subject_name.id))
        sql_results = self.env.cr.dictfetchall()
        for i in xrange(len(sql_results)):
            direction_tuple = self.judgment_lending(sql_results[i]['credit'], sql_results[i]['debit'])
            sql_results[i].update({'direction': direction_tuple[0],
                                   'balance': direction_tuple[1]})
        return sql_results

    @api.multi
    def get_unclose_year_balance(self, initial_balance, period, subject_name):
        sql = ''' select  sum(vol.debit)as debit,sum(vol.credit) as credit
         from voucher as vo left join voucher_line as vol
            on vo.id = vol.voucher_id where vo.period_id=%s and  vol.account_id=%s
                 group by vol.account_id'''
        self.env.cr.execute(sql, (period.id, subject_name.id))
        sql_results = self.env.cr.dictfetchall()
        year_balance_debit = sql_results[0].get('debit') + initial_balance.get('debit', 0)
        year_balance_credit = sql_results[0].get('credit') + initial_balance.get('credit', 0)
        direction_tuple = self.judgment_lending(year_balance_credit, year_balance_debit)
        initial_balance.update({
            'date': (datetime.now()).strftime(ISODATEFORMAT),
            'direction': direction_tuple[0],
            'balance': direction_tuple[1],
            'debit': year_balance_debit,
            'credit': year_balance_credit,
            'summary': u'本年累计发生额'
        })
        return initial_balance

    @api.multi
    def create_vouchers_summary(self):
        last_period = self.env['create.trial.balance.wizard'].compute_last_period_id(self.period_begin_id)
        if not last_period:
            raise except_orm(u'错误', u'上一个期间不存在,无法取到期初余额')
        if not last_period.is_closed:
            raise except_orm(u'错误', u'前一期间未结账，无法取到期初余额')
        # period_end = self.env['create.trial.balance.wizard'].compute_next_period_id(self.period_end_id)
        local_last_period = last_period
        local_currcy_period = self.period_begin_id
        vouchers_summary_ids = []
        break_flag = True
        create_vals = []
        while (break_flag):
            initial_balance = self.get_initial_balance(local_last_period, self.subject_name_id.id)
            create_vals.append(initial_balance)
            occurrence_amount = self.get_current_occurrence_amount(local_currcy_period, self.subject_name_id)
            create_vals += occurrence_amount
            if local_currcy_period.id != self.period_end_id.id:
                cumulative_year_occurrence = self.get_year_balance(local_currcy_period, self.subject_name_id)
            else:
                cumulative_year_occurrence = self.get_unclose_year_balance(initial_balance, local_currcy_period, self.subject_name_id)
            create_vals.append(cumulative_year_occurrence)
            if local_currcy_period.id == self.period_end_id.id:
                break_flag = False
            local_currcy_period = self.env['create.trial.balance.wizard'].compute_next_period_id(local_currcy_period)
            local_last_period = self.env['create.trial.balance.wizard'].compute_last_period_id(local_currcy_period)

        print create_vals
        for vals in create_vals:
            vouchers_summary_ids.append(self.env['vouchers.summary'].create(vals).id)
        view_id = self.env.ref('finance.vouchers_summary_tree').id
        return {
            'type': 'ir.actions.act_window',
            'name': '期末余额表',
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'vouchers.summary',
            'target': 'current',
            'view_id': False,
            'views': [(view_id, 'tree')],
            'domain': [('id', 'in', vouchers_summary_ids)]
        }


class VouchersSummary(models.TransientModel):
    _name = 'vouchers.summary'
    date = fields.Date(u'日期')
    subject_name_id = fields.Many2one('finance.account', string='科目名称')
    period_id = fields.Many2one('finance.period', string='会计区间')
    voucher_id = fields.Many2one('voucher', u'凭证字号')
    summary = fields.Char(u'摘要')
    direction = fields.Char(u'方向')
    debit = fields.Float(u'借方金额')
    credit = fields.Float(u'贷方金额')
    balance = fields.Float(u'余额')
