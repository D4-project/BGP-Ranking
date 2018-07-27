function linegraph(call_path) {
    var canvas = document.querySelector("canvas"),
        context = canvas.getContext("2d");

    // set the dimensions and margins of the graph
    var margin = {top: 20, right: 20, bottom: 30, left: 50},
        width = canvas.width - margin.left - margin.right,
        height = canvas.height - margin.top - margin.bottom;

    // parse the date / time
    var parseTime = d3.timeParse("%Y-%m-%d");

    // set the ranges
    var x = d3.scaleTime().range([0, width]);
    var y = d3.scaleLinear().range([height, 0]);

    // define the line
    var line = d3.line()
        .x(function(d) { return x(parseTime(d[0])); })
        .y(function(d) { return y(d[1]); })
        .curve(d3.curveStep)
        .context(context);

    context.translate(margin.left, margin.top);

    // Get the data
    d3.json(call_path, {credentials: 'same-origin'}).then(function(data) {
      x.domain(d3.extent(data, function(d) { return parseTime(d[0]); }));
      y.domain(d3.extent(data, function(d) { return d[1]; }));

      xAxis();
      yAxis();

      context.beginPath();
      line(data);
      context.lineWidth = 1.5;
      context.strokeStyle = "steelblue";
      context.stroke();
    });

    function xAxis() {
      var tickCount = 10,
          tickSize = .1,
          ticks = x.ticks(tickCount),
          tickFormat = x.tickFormat();

      context.beginPath();
      ticks.forEach(function(d) {
        context.moveTo(x(d), height);
        context.lineTo(x(d), height + tickSize);
      });
      context.strokeStyle = "black";
      context.stroke();

      context.textAlign = "center";
      context.textBaseline = "top";
      ticks.forEach(function(d) {
        context.fillText(tickFormat(d), x(d), height + tickSize);
      });
    }

    function yAxis() {
      var tickCount = 20,
          tickSize = 1,
          tickPadding = 1,
          ticks = y.ticks(tickCount),
          tickFormat = y.tickFormat(tickCount);

      context.beginPath();
      ticks.forEach(function(d) {
        context.moveTo(0, y(d));
        context.lineTo(-6, y(d));
      });
      context.strokeStyle = "black";
      context.stroke();

      context.beginPath();
      context.moveTo(-tickSize, 0);
      context.lineTo(0.5, 0);
      context.lineTo(0.5, height);
      context.lineTo(-tickSize, height);
      context.strokeStyle = "black";
      context.stroke();

      context.textAlign = "right";
      context.textBaseline = "middle";
      ticks.forEach(function(d) {
        context.fillText(tickFormat(d), -tickSize - tickPadding, y(d));
      });

      context.save();
      context.rotate(-Math.PI / 2);
      context.textAlign = "right";
      context.textBaseline = "top";
      context.font = "bold 10px sans-serif";
      context.fillText("Rank", -10, 10);
      context.restore();
    }
}
