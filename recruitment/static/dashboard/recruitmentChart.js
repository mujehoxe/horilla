$(document).ready(function () {
  function recruitmentChart(dataSet, labels) {
    const data = {
      labels: labels,
      datasets: dataSet,
    };
    // Create chart using the Chart.js library
    window['myChart'] = {}
    const ctx = document.getElementById("recruitmentChart1").getContext("2d");
    myChart = new Chart(ctx, {
      type: 'bar',
      data: data,
      options: {
      },
    });
  }
  $.ajax({
    url: "/recruitment/dashboard-pipeline",
    type: "GET",
    success: function (response) {
      // Code to handle the response
      // response =  {'dataSet': [{'label': 'Odoo developer 2023-03-30', 'data': [3, 0, 5, 3]}, {'label': 'React developer 2023-03-31', 'data': [0, 1, 1, 0]}, {'label': 'Content Writer 2023-04-01', 'data': [1, 0, 0, 0]}], 'labels': ['Initial', 'Test', 'Interview', 'Hired']}
      dataSet = response.dataSet;
      labels = response.labels;
      recruitmentChart(dataSet, labels);
    },
  });

  $('.oh-card-dashboard__title').click(function (e) { 
    var chartType = myChart.config.type
    if (chartType === 'line') {
      chartType = 'bar';
    } else if(chartType==='bar') {
        chartType = 'doughnut';
    } else if(chartType==='doughnut'){
      chartType = 'pie'
    }else if(chartType==='pie'){
      chartType = 'line'
    }
    myChart.config.type = chartType;
    myChart.update();    
  });
    
});
