/* Rank history charts (Apache ECharts), styled like the rest of the UI.
 * asnChart(url)     — /json/asn_history     -> [[date, rank], ...]
 * countryChart(url) — /json/country_history -> {CC: [[date, rank, details], ...]}
 */
"use strict";

var CHART_COLORS = ['#de2d38', '#315e73', '#e4a526', '#2f9e6e', '#8a4fbf', '#d9772b', '#1f8fb3', '#c2185b',
  '#6b8e23', '#7b5e57', '#e0609a', '#4c6ef5', '#9c2f3a', '#00897b', '#b08900', '#5d717c'];
// Beyond the fixed palette, spread extra series around the colour wheel.
function colorsFor(n) {
  var out = CHART_COLORS.slice(0, n);
  for (var i = out.length; i < n; i++) out.push('hsl(' + Math.round((i * 137.5) % 360) + ', 55%, 48%)');
  return out;
}
var TEXT = '#23313a', MUTED = '#5d717c', LINE = '#dce4e8', PANEL = '#fff';
var CHARTS = [];

// Chart colours come from the page's CSS variables, so charts follow the light / dark theme.
function refreshColors() {
  var cs = getComputedStyle(document.documentElement);
  function v(name, fallback) { return (cs.getPropertyValue(name) || '').trim() || fallback; }
  TEXT = v('--text', TEXT); MUTED = v('--muted', MUTED); LINE = v('--line', LINE); PANEL = v('--panel', PANEL);
}

// Colour-only part of the options, re-applied when the theme changes.
function themeOption() {
  return {
    textStyle: {color: TEXT},
    tooltip: {backgroundColor: PANEL, borderColor: LINE, textStyle: {color: TEXT}},
    xAxis: {axisLine: {lineStyle: {color: LINE}}, axisLabel: {color: MUTED}},
    yAxis: {nameTextStyle: {color: MUTED}, splitLine: {lineStyle: {color: LINE}}, axisLabel: {color: MUTED}}
  };
}

document.addEventListener('bgpr-theme', function () {
  refreshColors();
  CHARTS.forEach(function (c) {
    if (c.isDisposed()) return;
    c.setOption(themeOption());
    if ((c.getOption().legend || []).length) c.setOption({legend: {textStyle: {color: TEXT}}});
    if (c._updateEmpty) c._updateEmpty();
  });
});

function fmtRank(v) {
  if (v === null || v === undefined || isNaN(v)) return '–';
  if (v === 0) return '0';
  if (Math.abs(v) < 0.001) return v.toExponential(2);
  return (+v.toPrecision(4)).toString();
}

function fmtDate(iso) {
  var d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString(undefined, {day: 'numeric', month: 'short', year: 'numeric'});
}

// Very small ranks (IPv6 address space is huge, so ranks are ~1e-18) break axis ticks.
// Plot value × 10^k instead and show the unit on the axis; tooltips keep the real value.
function scaleFor(values) {
  var max = Math.max.apply(null, values.map(Math.abs).concat([0]));
  if (!max || max >= 1e-3) return {k: 0, factor: 1};
  var k = -Math.floor(Math.log10(max));
  return {k: k, factor: Math.pow(10, k)};
}
var SUP = {'-': '⁻', 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹'};
function applyScale(opt, sc) {
  if (!sc.k) return;
  opt.yAxis.name = 'Rank (×10' + String(-sc.k).split('').map(function (c) { return SUP[c]; }).join('') + ')';
  opt.yAxis.axisLabel.formatter = function (v) { return +v.toPrecision(3); };
}

function chartDone(id, message) {
  document.querySelectorAll('#' + id + '-wrap > .chart-loader').forEach(function (el) {
    if (message) { el.classList.add('failed'); el.innerHTML = '<span>' + message + '</span>'; }
    else { el.remove(); }
  });
}

function baseOption(dates) {
  refreshColors();
  return {
    animationDuration: 600,
    textStyle: {fontFamily: 'Raleway, system-ui, sans-serif', color: TEXT},
    // containLabel: the grid makes room for long y labels instead of letting them overflow the card.
    grid: {left: 22, right: 30, top: 34, bottom: 8, containLabel: true},
    tooltip: {
      trigger: 'axis',
      backgroundColor: PANEL, borderColor: LINE, borderWidth: 1, padding: [8, 12],
      textStyle: {color: TEXT, fontSize: 13},
      axisPointer: {type: 'line', lineStyle: {color: '#de2d38', type: 'dashed'}}
    },
    xAxis: {
      type: 'category', data: dates, boundaryGap: false,
      axisLine: {lineStyle: {color: LINE}}, axisTick: {show: false},
      axisLabel: {color: MUTED, formatter: function (v) { return fmtDate(v).replace(/ \d{4}$/, ''); }}
    },
    yAxis: {
      type: 'value', name: 'Rank', nameTextStyle: {color: MUTED, align: 'left', padding: [0, 0, 0, -18]},
      splitLine: {lineStyle: {color: LINE, type: 'dashed'}},
      axisLabel: {color: MUTED, formatter: fmtRank}
    },
    // No user zoom: the period is only changed with the 30 d / 60 d / All buttons.
    dataZoom: [{type: 'inside', start: 0, end: 100, zoomOnMouseWheel: false, moveOnMouseMove: false, moveOnMouseWheel: false, preventDefaultMouseMove: false}]
  };
}

// Discreet "?" next to each axis, explaining how to read it.
var AXIS_HELP = {
  y: 'Vertical axis — rank of the day: malicious IPs weighted by the reliability of their list, divided by the address space. 0 = nothing reported, higher = worse. "×10⁻ⁿ" means the values are shown multiplied to stay readable (IPv6 ranks are tiny).',
  x: 'Horizontal axis — one point per day. Use 30 d / 60 d / All to change the period.'
};
function addAxisHelp(id) {
  var wrap = document.getElementById(id + '-wrap');
  if (!wrap || wrap.querySelector('.axis-help')) return;
  ['y', 'x'].forEach(function (a) {
    var i = document.createElement('i');
    i.className = 'fa fa-question-circle axis-help axis-help-' + a;
    i.title = AXIS_HELP[a];
    i.tabIndex = 0;
    i.setAttribute('aria-label', AXIS_HELP[a]);
    wrap.appendChild(i);
  });
}

function makeChart(id) {
  addAxisHelp(id);
  var chart = echarts.init(document.getElementById(id), null, {renderer: 'canvas'});
  window.addEventListener('resize', function () { chart.resize(); });
  CHARTS.push(chart);
  return chart;
}

// Range buttons (30d / 60d / All) above a chart.
function bindRanges(id, chart, total) {
  document.querySelectorAll('[data-range-for="' + id + '"] button').forEach(function (b) {
    b.addEventListener('click', function () {
      var days = +b.dataset.days;
      var start = days && total > days ? 100 - (days / total) * 100 : 0;
      chart.dispatchAction({type: 'dataZoom', start: start, end: 100});
      b.parentNode.querySelectorAll('button').forEach(function (o) { o.classList.toggle('on', o === b); });
    });
  });
}

// Show a note when every value in the visible period is 0, so a flat line is not mistaken for a bug.
function watchEmpty(chart, what) {
  function update() {
    var o = chart.getOption(), n = o.xAxis[0].data.length, z = o.dataZoom[0];
    var from = Math.floor((z.start / 100) * (n - 1)), to = Math.ceil((z.end / 100) * (n - 1));
    var empty = o.series.every(function (s) {
      return s.data.slice(from, to + 1).every(function (v) { return !v; });
    });
    var v6 = document.querySelector('.segmented [value="v6"].on') ? ' in IPv6' : '';
    chart.setOption({graphic: [{id: 'empty-note', type: 'text', left: 'center', top: '40%', silent: true, invisible: !empty,
      style: {text: 'No malicious activity recorded for ' + what + ' over this period' + v6 + '.',
              fill: MUTED, fontSize: 14, fontFamily: 'Raleway, sans-serif'}}]});
  }
  chart.on('dataZoom', update);
  chart.on('finished', function once() { chart.off('finished', once); update(); });
  chart._updateEmpty = update;
}

// Line / bar switch above a chart: rebuilds the chart from its original option.
function bindTypes(id, chart, opt) {
  document.querySelectorAll('[data-type-for="' + id + '"] button').forEach(function (b) {
    b.addEventListener('click', function () {
      var type = b.dataset.type, bar = type === 'bar', dots = type === 'scatter';
      var zoom = chart.getOption().dataZoom[0];
      var o = Object.assign({}, opt, {
        xAxis: Object.assign({}, opt.xAxis, {boundaryGap: bar}),
        dataZoom: [Object.assign({}, opt.dataZoom[0], {start: zoom.start, end: zoom.end})],
        series: opt.series.map(function (s) {
          var copy = Object.assign({}, s, {type: type, barMaxWidth: 14});
          if (bar || dots) { delete copy.areaStyle; delete copy.showSymbol; delete copy.lineStyle; }
          if (dots) { copy.symbolSize = 7; copy.itemStyle = Object.assign({}, s.itemStyle, {opacity: .85}); }
          return copy;
        })
      });
      chart.setOption(o, true);
      chart.setOption(themeOption());
      if (chart._updateEmpty) chart._updateEmpty();
      b.parentNode.querySelectorAll('button').forEach(function (x) { x.classList.toggle('on', x === b); });
    });
  });
}

function setStats(id, stats) {
  var box = document.getElementById(id + '-stats');
  if (!box) return;
  box.innerHTML = stats.map(function (s) {
    return '<div class="stat"><span class="stat-label">' + s[0] + '</span><span class="stat-value ' + (s[2] || '') + '">' + s[1] + '</span></div>';
  }).join('');
}

function asnChart(url) {
  var id = 'asn-chart';
  fetch(url, {credentials: 'same-origin'}).then(function (r) {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }).then(function (data) {
    var rows = (data && data.response) || [];
    if (!rows.length) { chartDone(id, 'No history available.'); return; }
    var dates = rows.map(function (r) { return r[0]; });
    var ranks = rows.map(function (r) { return r[1]; });
    chartDone(id);

    var active = ranks.filter(function (v) { return v > 0; });
    var avg = active.length ? active.reduce(function (a, b) { return a + b; }, 0) / active.length : 0;
    var maxV = Math.max.apply(null, ranks), maxDate = dates[ranks.indexOf(maxV)];
    var last = ranks[ranks.length - 1], prev = ranks[ranks.length - 2];
    var delta = prev ? (last - prev) / prev * 100 : null;

    var chart = makeChart(id);
    var opt = baseOption(dates);
    var sc = scaleFor(ranks);
    applyScale(opt, sc);
    opt.tooltip.formatter = function (p) {
      return fmtDate(dates[p[0].dataIndex]) + '<br><b>' + fmtRank(ranks[p[0].dataIndex]) + '</b>';
    };
    opt.series = [{
      name: 'Rank', type: 'line', data: ranks.map(function (v) { return v * sc.factor; }), showSymbol: false, symbolSize: 7,
      lineStyle: {width: 2.5, color: '#de2d38'}, itemStyle: {color: '#de2d38'},
      areaStyle: {color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        {offset: 0, color: 'rgba(222,45,56,.18)'}, {offset: 1, color: 'rgba(222,45,56,0)'}])}
    }];
    // Skip the leading run of zeros (no data yet) so the interesting part fills the chart.
    var first = ranks.findIndex(function (v) { return v > 0; });
    if (first > 3) {
      var startPct = Math.max(0, (first - 3) / dates.length * 100);
      opt.dataZoom[0].start = startPct;
      document.querySelectorAll('[data-range-for="' + id + '"] button').forEach(function (b) { b.classList.remove('on'); });
    }
    chart.setOption(opt);
    bindRanges(id, chart, dates.length);
    bindTypes(id, chart, opt);
    watchEmpty(chart, 'this AS');
  }).catch(function () { chartDone(id, 'Could not load the ranking history.'); });
}

// One row per AS that had activity in the period, worst first; zeros are left out.
function renderCountryTable(resp, dates) {
  var box = document.getElementById('asn_details');
  var PAGE = 50;
  var html = '';
  Object.keys(resp).forEach(function (country) {
    var per = {};
    resp[country].forEach(function (day, i) {
      (day[2] || []).forEach(function (d) {
        var r = +d[1];
        if (!r) return;
        var e = per[d[0]] || (per[d[0]] = {asn: d[0], sum: 0, peak: 0, days: 0, last: 0});
        e.sum += r; e.days += 1; e.peak = Math.max(e.peak, r);
        if (i === dates.length - 1) e.last = r;
      });
    });
    var rows = Object.keys(per).map(function (k) { return per[k]; }).sort(function (a, b) { return b.sum - a.sum; });
    var total = (resp[country][resp[country].length - 1][2] || []).length;
    html += '<div class="country-table" data-country="' + country + '">' +
      '<p class="country-table-head"><b>' + country + '</b> — ' + rows.length + ' of ' + total +
      ' autonomous systems had malicious activity over the period</p>';
    if (!rows.length) { html += '<p class="empty">Nothing reported for ' + country + ' over this period.</p></div>'; return; }
    html += '<table class="table"><thead><tr><th class="pos">#</th><th>ASN</th>' +
      '<th class="num" title="Rank on the last day of the period">Latest</th>' +
      '<th class="num" title="Highest daily rank over the period">Peak</th>' +
      '<th class="num" title="Average over the days with activity">Average</th>' +
      '<th class="num" title="Days with at least one malicious IP reported">Active days</th></tr></thead><tbody>';
    rows.forEach(function (e, i) {
      html += '<tr class="' + (i >= PAGE ? 'more-row' : '') + '"><td class="pos">' + (i + 1) + '</td>' +
        '<td class="mono"><a href="/asn?asn=' + e.asn + '">AS' + e.asn + '</a></td>' +
        '<td class="num">' + (e.last ? fmtRank(e.last) : '<span class="zero">·</span>') + '</td>' +
        '<td class="num">' + fmtRank(e.peak) + '</td>' +
        '<td class="num">' + fmtRank(e.sum / e.days) + '</td>' +
        '<td class="num">' + e.days + ' / ' + dates.length + '</td></tr>';
    });
    html += '</tbody></table>';
    if (rows.length > PAGE) {
      html += '<p class="show-more"><button type="button" class="btn btn-outline-secondary btn-sm">Show all ' + rows.length + '</button></p>';
    }
    html += '</div>';
  });
  box.innerHTML = html;
  box.querySelectorAll('.show-more button').forEach(function (b) {
    b.addEventListener('click', function () {
      b.closest('.country-table').classList.add('expanded');
      b.parentNode.remove();
    });
  });
}

// After a few seconds, tell the user why the loader is still there.
function slowNotice(id, ms) {
  var t0 = Date.now();
  return setInterval(function () {
    var secs = Math.round((Date.now() - t0) / 1000);
    if (secs * 1000 < ms) return;
    var l = document.querySelector('#' + id + '-wrap > .chart-loader span:last-child');
    if (l) l.innerHTML = 'Still loading… ' + secs + ' s<br><small>The server computes every autonomous system of each selected country;' +
      ' large countries take about 30 s each.</small>';
  }, 1000);
}

function countryChart(url) {
  var id = 'country-chart';
  var slow = slowNotice(id, 5000);
  fetch(url, {credentials: 'same-origin'}).then(function (r) {
    if (!r.ok) throw new Error(r.status >= 500 ? 'The server could not finish computing these countries (error ' + r.status + '). Try with fewer or smaller countries.' : 'Error ' + r.status);
    return r.json();
  }).then(function (data) {
    var resp = (data && data.response) || {};
    clearInterval(slow);
    var countries = Object.keys(resp);
    if (!countries.length) { chartDone(id, 'No data for the selected countries.'); return; }
    var dates = resp[countries[0]].map(function (r) { return r[0]; });
    chartDone(id);


    var chart = makeChart(id);
    var opt = baseOption(dates);
    opt.color = colorsFor(countries.length);
    // Many countries: scrollable legend on one line, and leave room for it.
    opt.legend = {type: 'scroll', top: 4, left: 40, right: 40, icon: 'roundRect', itemWidth: 14, itemHeight: 4,
      textStyle: {color: TEXT}, pageIconColor: '#de2d38', pageTextStyle: {color: MUTED}};
    opt.grid.top = 48;
    opt.tooltip.confine = true;
    if (countries.length > 12) {
      // Long tooltips: only the 12 highest values of the hovered day.
      opt.tooltip.formatter = function (ps) {
        var list = ps.slice().sort(function (a, b) { return b.value - a.value; });
        var rows = list.slice(0, 12).map(function (p) { return p.marker + p.seriesName + ' <b style="float:right;margin-left:1.2em">' + fmtRank(p.value / sc.factor) + '</b>'; });
        if (list.length > 12) rows.push('<span style="color:' + MUTED + '">+ ' + (list.length - 12) + ' more</span>');
        return '<b>' + fmtDate(ps[0].axisValue) + '</b><br>' + rows.join('<br>');
      };
    }
    opt.tooltip.order = 'valueDesc';
    var sc = scaleFor([].concat.apply([], countries.map(function (c) { return resp[c].map(function (r) { return r[1]; }); })));
    applyScale(opt, sc);
    opt.tooltip.valueFormatter = function (v) { return fmtRank(v / sc.factor); };
    opt.series = countries.map(function (c) {
      return {name: c, type: 'line', data: resp[c].map(function (r) { return r[1] * sc.factor; }),
        showSymbol: false, lineStyle: {width: 2.2}, emphasis: {focus: 'series'}};
    });
    chart.setOption(opt);
    bindRanges(id, chart, dates.length);
    bindTypes(id, chart, opt);
    watchEmpty(chart, 'these countries');

    // Per-AS table built here from the data already received (the backend version renders every AS
    // of the country for every day, which is ~10 MB of HTML for a large country and freezes the browser).
    renderCountryTable(resp, dates);
  }).catch(function (err) {
    clearInterval(slow);
    chartDone(id, err instanceof TypeError ? 'The server stopped responding before the computation ended (too many or too large countries for its time limit).'
      : (err && err.message && err.message.length > 12) ? err.message : 'Could not load the ranking history.');
    document.getElementById('asn_details').innerHTML = '<p class="empty">Could not load the autonomous systems.</p>';
  });
}
