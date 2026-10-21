import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_bovinos as bov

HTML = '''<!doctype html><html><body>
<div>Atualizado 21/10/26</div>
<section><h2>Gado Gordo · Semana Atual</h2><div>PV Macho R$ 13,00 ● 0,0%</div><div>PC Macho R$ 25,20</div><div>PV Fêmea R$ 11,05</div><div>PC Fêmea R$ 22,30</div><div>Terneiro 6-12m R$ 15,30</div><div>Novilho 13-24m R$ 12,61</div><div>Vaca Invernar R$ 10,90</div><div>Vaca Prenhe R$ 12,10</div><div>Terneira 6-12m R$ 15,05</div><div>Novilha 13-24m R$ 13,55</div></section>
<h2>Análise Técnica Semanal</h2>
<h2>Últimas 8 semanas</h2>
<table><thead><tr><th>Data</th><th>PV Macho</th><th>Δ%</th><th>PV Fêmea</th><th>Δ%</th><th>Terneiro</th><th>Δ%</th><th>Novilho</th><th>Δ%</th></tr></thead><tbody>
<tr><td>21/10/26</td><td>13,00</td><td>+1,0%</td><td>11,05</td><td>0%</td><td>15,30</td><td>0%</td><td>12,61</td><td>0%</td></tr>
<tr><td>14/10/26</td><td>12,65</td><td>0%</td><td>10,50</td><td>0%</td><td>14,90</td><td>0%</td><td>12,36</td><td>0%</td></tr></tbody></table>
</body></html>'''

class TestNESPro(unittest.TestCase):
    def test_page(self):
        d, rows = bov.parse_page(HTML)
        self.assertEqual(d,'2026-10-21')
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[d]['pc_macho'],25.2)
        self.assertEqual(rows['2026-10-14']['terneiro'],14.9)
    def test_malformed(self):
        with self.assertRaises(ValueError):
            bov.parse_page('<html><p>site indisponível</p></html>')
    def test_csv(self):
        entries = {'2026-10-21':{'data':'2026-10-21','pv_macho':13.0,'terneiro':15.30}}
        encoded = bov.serialize_csv(entries)
        self.assertIn('2026-10-21;13,00;',encoded)
    def test_no_fake_date(self):
        with self.assertRaises(ValueError):
            bov.update(HTML,today=bov.date(2026,10,10),persist=False)

if __name__ == '__main__': unittest.main()
