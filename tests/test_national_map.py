import pandas as pd
import pytest

from eleicoes.national_map import map_color,feature_rows,static_maps


def test_change_colors_are_symmetric_and_distinct_from_final_leadership():
    a=map_color({'margin_change_pp':40},'margin')
    b=map_color({'margin_change_pp':-40},'margin')
    assert int(a[5:7],16)>int(a[1:3],16)
    assert int(b[1:3],16)>int(b[5:7],16)
    assert map_color({'margin_change_pp':0},'margin')=='#ffffff'
    assert map_color({'margin_change_pp':None},'margin')=='#c5cbd3'
    row={'votes_22_2':90,'votes_13_2':10,'margin_change_pp':-20}
    assert map_color(row,'winner')!=map_color(row,'margin')


@pytest.mark.parametrize('eligible,coverage,expected',[(0,100,'#c5cbd3'),(10,100,'#c5cbd3'),(40,79,'#c5cbd3'),(40,90,'#ffffff')])
def test_rate_zero_is_white_only_with_usable_denominator(eligible,coverage,expected):
    assert map_color({'eligible_sections':eligible,'eligible_coverage_pct':coverage,'rate_per_1000':0},'rate')==expected


def test_static_map_orientation_keeps_north_above_south(tmp_path,monkeypatch):
    from matplotlib.figure import Figure
    actual=[]
    def inspect(fig,*args,**kwargs):
        ax=fig.axes[0]
        actual.append(ax.transData.transform((-40,-5))[1]>ax.transData.transform((-40,30))[1])
    monkeypatch.setattr(Figure,'savefig',inspect)
    rows=[dict(path='M-41,-5L-39,-5L-39,30L-41,30Z',margin_change_pp=10,eligible_sections=50,eligible_coverage_pct=90,rate_per_1000=100)]
    static_maps(tmp_path,rows,30,80)
    assert actual==[True,True]
