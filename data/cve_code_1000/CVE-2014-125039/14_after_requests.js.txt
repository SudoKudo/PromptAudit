var MInterpreterBrowseRequests_Implementation = {
  extend: "NeoX.TBaseObject",
  type: "module",
  construct: function() {
  	this.base(this);
  },
  
  methods: {
    
    init: function() {
      //nothing to init
    },
        
    /*
     * AJAX REQUESTS
     */
    
    load: function(page) {
      $.ajax({
        type: "POST",
        url: NeoX.Modules.InterpreterBrowseIndex.getConfig().moduleScript,
        dataType: 'json',
        data: {
          'type': NeoX.Modules.InterpreterBrowseIndex.getConfig().moduleType,
          'action': 'load',
          'page': page
        },
        success: NeoX.Modules.InterpreterBrowseRequests.loadCallback
      });
    },
    
    save: function(id, rep, container) {
    	$.ajax({
        type: "POST",
        url: NeoX.Modules.InterpreterBrowseIndex.getConfig().moduleScript,
        dataType: 'json',
        data: {
          'type': NeoX.Modules.InterpreterBrowseIndex.getConfig().moduleType,
          'action': 'save',
          'sentenceID': id,
          'newValue': rep
        },
        success: NeoX.Modules.InterpreterBrowseRequests.saveCallback(rep, container)
      });
    },
    
    resplit: function(id, container) {
    	$.ajax({
        type: "POST",
        url: NeoX.Modules.InterpreterBrowseIndex.getConfig().moduleScript,
        dataType: 'json',
        data: {
          'type': NeoX.Modules.InterpreterBrowseIndex.getConfig().moduleType,
          'action': 'resplit',
          'sentenceID': id
        },
        success: NeoX.Modules.InterpreterBrowseRequests.resplitCallback(container)
      });
    },
    
    /*
     * AJAX SUCCESS CALLBACKS
     */
    
    loadCallback: function(json) {
    	$(NeoX.Modules.InterpreterBrowseIndex.getConfig().dataContainer).html(json['data']);
    	$(NeoX.Modules.InterpreterBrowseIndex.getConfig().paginationContainer).html(json['pagination']);
    	if(json['pagination'] == "") {
        $(".buttons.smaller").hide();
      } else {
        $(".buttons.smaller").show();
      }
    },
    
    saveCallback: function(newValue, container) {
      return function(json) {
        if(json && json['ErrorString'] && json['StrIndex']) {
          var near = newValue.substr(json['StrIndex'], newValue.length);
          container.find('.rep-error').remove();
          container.append("<br/><div class='rep-error' style='color: red'><br/>" + json['ErrorString'] + " at \"" + near + "\"</div>");
        } else {
          container.text(newValue);
        }
      };
    },
    
    resplitCallback: function(container) {
      return function(json) {
        container.nextUntil(".aproto").remove();
        container.remove();
      };
    }
       
    
  }

};

Sky.Class.Define("NeoX.Modules.InterpreterBrowseRequests", MInterpreterBrowseRequests_Implementation);
