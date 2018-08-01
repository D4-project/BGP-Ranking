function linegraph(call_path) {
	var svg = d3.select("svg"),
		margin = {top: 20, right: 80, bottom: 30, left: 50},
		width = svg.attr("width") - margin.left - margin.right,
		height = svg.attr("height") - margin.top - margin.bottom,
		g = svg.append("g").attr("transform", "translate(" + margin.left + "," + margin.top + ")");

	var parseTime = d3.timeParse("%Y-%m-%d");

	var x = d3.scaleTime().range([0, width]),
		y = d3.scaleLinear().range([height, 0]),
		z = d3.scaleOrdinal(d3.schemeCategory10);

	var line = d3.line()
		.curve(d3.curveBasis)
		.x(function(d) { return x(d.date); })
		.y(function(d) { return y(d.rank); });

	d3.json(call_path, {credentials: 'same-origin'}).then(function(data) {

	  var country_ranks = d3.entries(data).map(function(country_rank) {
        x.domain(d3.extent(country_rank.value, function(d) { return parseTime(d[0]); }));
		return {
		  country: country_rank.key,
		  values: d3.values(country_rank.value).map(function(d) {
			return {date: parseTime(d[0]), rank: d[1]};
		  })
		};
	  });

	  y.domain([
		d3.min(country_ranks, function(c) { return d3.min(c.values, function(d) { return d.rank; }); }),
		d3.max(country_ranks, function(c) { return d3.max(c.values, function(d) { return d.rank; }); })
	  ]);

	  z.domain(country_ranks.map(function(c) { return c.country; }));

	  g.append("g")
		  .attr("class", "axis axis--x")
		  .attr("transform", "translate(0," + height + ")")
		  .call(d3.axisBottom(x));

	  g.append("g")
		  .attr("class", "axis axis--y")
		  .call(d3.axisLeft(y))
		.append("text")
		  .attr("transform", "rotate(-90)")
		  .attr("y", 6)
		  .attr("dy", "0.71em")
		  .attr("fill", "#000")
		  .text("Rank");

	  var country = g.selectAll(".country")
		.data(country_ranks)
		.enter().append("g")
		  .attr("class", "country");

	  country.append("path")
		  .attr("class", "line")
		  .attr("d", function(d) { return line(d.values); })
		  .style("stroke", function(d) { return z(d.country); });

	  country.append("text")
		  .datum(function(d) { return {id: d.country, value: d.values[d.values.length - 1]}; })
		  .attr("transform", function(d) { return "translate(" + x(d.value.date) + "," + y(d.value.rank) + ")"; })
		  .attr("x", 3)
		  .attr("dy", "0.35em")
		  .style("font", "10px sans-serif")
		  .text(function(d) { return d.id; });

      d3.json(call_path + '_callback',
                  {credentials: 'same-origin',
                   method: 'POST',
                   body: JSON.stringify(data),
                   // headers: {'Content-Type': 'application/json'}
                  }).then(function(data) {
            d3.select('#asn_details').html(data);
      });
    });
};
