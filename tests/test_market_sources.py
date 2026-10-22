import io
import csv
from datetime import date
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'scripts'))
import update_market_sources as u

class CollectorsTest(unittest.TestCase):
    def test_cepea_selects_paranagua_not_parana(self):
        html='''<h2>INDICADOR DA SOJA CEPEA/ESALQ - PARANAGUÁ</h2>
        <table><tr><th>Data</th><th>Valor R$</th><th>Var./Dia</th><th>Var./Mês</th><th>Valor US$</th></tr>
        <tr><td>20/10/2026</td><td>159,43</td><td>0,1%</td><td>0%</td><td>29,20</td></tr></table>
        <h2>INDICADOR DA SOJA CEPEA/ESALQ - PARANÁ</h2>
        <table><tr><th>Data</th><th>Valor R$</th></tr><tr><td>20/10/2026</td><td>148,90</td></tr></table>'''
        records = u.parse_cepea(html, today=date(2026,10,21))
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['brl_saca60'],159.43)
        self.assertEqual(records[0]['usd_saca60'],29.2)
    def test_secondary_requires_explicit_date(self):
        html='<p>Indicadores CEPEA/ESALQ, apuração de 20 de outubro de 2026, atualizado às 05:15.</p><table><tr><td>Soja Paranaguá</td><td>R$ 153,40</td><td>por sc de 60kg</td></tr></table>'
        rec=u.parse_cepea_secondary(html,today=date(2026,10,21))
        self.assertEqual(rec[0]['data'],'2026-10-20')
        self.assertEqual(rec[0]['brl_saca60'],153.40)
    def test_cepea_rejects_future(self):
        html='<h2>Paranaguá</h2><table><tr><td>24/10/2026</td><td>159,43</td></tr></table>'
        with self.assertRaises(ValueError): u.parse_cepea(html, today=date(2026,10,21))
    def test_usda_filter(self):
        r=[{'Commodity_Code':'2222000','Country_Code':'BR','Market_Year':str(y),'Attribute_Description':a,'Value':'170000'} for y in range(2010,2028) for a in ('Production','Domestic Consumption','Exports')]
        r+=[{'Commodity_Code':'2222000','Country_Code':'US','Market_Year':str(y),'Attribute_Description':a,'Value':'110000'} for y in range(2010,2028) for a in ('Production','Domestic Consumption','Exports')]
        r+=[{'Commodity_Code':'0440000','Country_Code':'BR','Market_Year':'2026','Attribute_Description':'Production','Value':'9999'}]
        with patch.object(u, 'now_br', return_value=__import__('datetime').datetime(2026,10,21)):
            got=u.parse_usda_rows(r)
        self.assertEqual(len(got),108)
        self.assertTrue(all(item['pais'] in ('BR','US') for item in got))
    def test_conab_brasil_production(self):
        class Sheet:
            name='Produção'
            grid=[['REGIÃO/UF', *[f'{year}/{str(year+1)[-2:]}' for year in range(2010,2026)]],
                  ['RS', *([50000]*16)],
                  ['BRASIL', *([150000]*16)]]
            nrows=len(grid)
            ncols=len(grid[0])
            def cell_value(self,row,col):return self.grid[row][col]
        class Book:
            def sheets(self):return [Sheet()]
        data=u.parse_conab_producao(Book())
        self.assertEqual(len(data),16)
        self.assertEqual(data[0]['producao_mil_ton'],150000)
    def test_cotrijuc_valid_local_soy_and_date(self):
        html = '''<h3>COTAÇÕES DO DIA</h3>
        <div>Grãos Boi Gordo 21/10/2026</div>
        <h4>SOJA</h4><p>135,50</p><h4>TRIGO</h4><p>73,00</p>
        <div>Bolsa de Chicago</div>'''
        record = u.parse_cotrijuc_soja(html, today=date(2026,10,21))
        self.assertEqual(record, {'data':'2026-10-21','brl_saca60':135.50})
        with self.assertRaises(ValueError):
            u.parse_cotrijuc_soja(html.replace('21/10/2026','23/10/2026'),today=date(2026,10,21))
    def test_cotrijuc_rejects_unidentifiable_quote(self):
        with self.assertRaises(ValueError):
            u.parse_cotrijuc_soja('<html><h4>SOJA</h4><p>136,90</p></html>',today=date(2026,10,21))
    def test_cbot_front_contract(self):
        html = """<h3>Soja - Bolsa de Chicago</h3>
          <table><tr><th>Contrato - Mês</th><th>Fechamento (US$ / Bushel)</th></tr>
          <tr><td>Novembro/26</td><td>12,4825</td></tr>
          <tr><td>Janeiro/27</td><td>12,6350</td></tr></table>
          <p>Atualizado em: 20/10/2026</p>"""
        v=u.parse_cbot_soja(html, today=date(2026,10,21))
        self.assertEqual(v['data'],'2026-10-20')
        self.assertEqual(v['contrato'],'2026-11')
        self.assertEqual(v['valor'],12.4825)
    def test_cbot_requires_fresh_contract_and_reference(self):
        html = '<p>Soja - Bolsa de Chicago Novembro/25 12,4825 Atualizado em: 20/10/2026</p>'
        with self.assertRaises(ValueError):
            u.parse_cbot_soja(html, today=date(2026,10,21))
    def test_milho_fechamento_datado(self):
        html = '''<h2>Indicador do Milho Esalq/B3</h2>
        <p>Fechamento: 20/10/2026</p>
        <table><tr><th>Data</th><th>Valor (R$/sc 60 kg)</th></tr>
        <tr><td>20/10/2026</td><td>64,34</td><td>-0,62%</td></tr></table>
        <h2>Milho B3</h2>'''
        found=u.parse_milho(html,today=date(2026,10,21))
        self.assertEqual(found['data'],'2026-10-20')
        self.assertEqual(found['brl_saca60'],64.34)

    def test_milho_data_divergente_rejeitada(self):
        html='<h2>Indicador do Milho Esalq/B3</h2>Fechamento: 20/10/2026 19/10/2026 64,34'
        with self.assertRaises(ValueError):
            u.parse_milho(html,today=date(2026,10,21))

    def test_valid_date(self):
        self.assertEqual(u.validate_day('14/10/2026',today=date(2026,10,21)),'2026-10-14')
        with self.assertRaises(ValueError): u.validate_day('01/02/2099',today=date(2026,10,21))

if __name__=='__main__':unittest.main()
