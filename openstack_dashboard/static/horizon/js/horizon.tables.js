/* Namespace for core functionality related to DataTables. */
horizon.datatables = {

};

horizon.datatables.add_no_results_row = function (table) {
  // Add a "no results" row if there are no results.
  template = horizon.templates.compiled_templates["#empty_row_template"];
  if (!table.find("div.list-group-item:visible").length 
      && typeof(template) !== "undefined") {
    table.append(template.render());
  }
};

horizon.datatables.remove_no_results_row = function (table) {
  table.find("p.empty").remove();
};

horizon.datatables.init_pagination = function (table) {
  var table_selector = table.attr('id');
  // init bootpag
  $('#'+table_selector+'_pagination_container').bootpag({
      total: table.attr('data-pagination-pages'),
      first: 'First',
      last:'Last',
      maxVisible: 10,
      wrapClass: 'pagination',
      firstLastUse: true
  }).on("page", function(event, num){ 
    horizon.ajax.queue({
      type: 'GET',
      url: table.attr('data-pagination-url'),
      data: {
        page: num,
        application_id: table.attr('data-application_id'),
        organization_id: table.attr('data-organization_id'),
      },
      beforeSend: function () {
        // add a spinner to show progress
        var list_group = $('#'+table_selector).find('div.list-group');
        list_group.html('<i class="fa fa-gear fa-spin"></i>');
      },
      complete: function () {
      },
      error: function(jqXHR, status, errorThrown) {
      },
      success: function (data, textStatus, jqXHR) {
        var list_group = $('#'+table_selector).find('div.list-group');
        list_group.empty();
        for (var i in data) {
          var display_name = data[i]['username'];
          if (display_name === undefined) {
            display_name = data[i]['name'];
          }
          var avatar = data[i]['img_small'];
          var data_id = data[i]['id'];
          var description = data[i]['description'];

          list_group.append('<div class="list-group-item">' +
            '<a class="item" href="/idm/organizations/'+ data_id + '/">' +
            '<div class="avatar filter_field"><img src="'+ avatar + '"></div>'+
            '<div class="name filter_field">'+ display_name +'</div>' + 
            '<div class="description filter_field">'+ description +'</div></a></div>');
        }
      }
    });
  });
};

horizon.datatables.set_table_query_filter = function (parent) {
  horizon.datatables.qs = {};
  $(parent).find('div.panel').each(function (index, elm) {
    var input = $($(elm).find('div.table_search.client input')),
        table_selector;
    if (input.length > 0) {
      // Disable server-side searching if we have client-side searching since
      // (for now) the client-side is actually superior. Server-side filtering
      // remains as a noscript fallback.
      // TODO(gabriel): figure out an overall strategy for making server-side
      // filtering the preferred functional method.
      input.on('keypress', function (evt) {
        if (evt.keyCode === 13) {
          return false;
        }
      });
      input.next('button.btn span.fa-search').on('click keypress', function (evt) {
        return false;
      });

      // Enable the client-side searching.
      table_selector = '#' + $(elm).find('div.list-group').attr('id');

      var qs = input.quicksearch(table_selector + ' div.list-group-item', {
        'delay': 300,
        'loader': 'span.loading',
        'bind': 'keyup click',
        'show': this.show,
        'hide': this.hide,
        onBefore: function () {
          var table = $(table_selector);
          horizon.datatables.remove_no_results_row(table);
        },
        onAfter: function () {
          var template, table, colspan, params;
          table = $(table_selector);
          horizon.datatables.add_no_results_row(table);
        },
        prepareQuery: function (val) {
          return new RegExp(val, "i");
        },
        testQuery: function (query, txt, _row) {
          return query.test($(_row).find('div.filter_field:not(.hidden):not(.actions_column)').text());
        }
      });
    }
  });
};


horizon.addInitFunction(function() {
  $('div.datatable').each(function (idx, el) {
    horizon.datatables.init_pagination($(el));
  });

  // Trigger run-once setup scripts for tables.
  horizon.datatables.set_table_query_filter($('body'));

  // Also apply on tables in modal views.
  horizon.modals.addModalInitFunction(horizon.datatables.set_table_query_filter);

  // Also apply on tables in tabs views for lazy-loaded data.
  horizon.tabs.addTabLoadFunction(horizon.datatables.set_table_query_filter);

});
