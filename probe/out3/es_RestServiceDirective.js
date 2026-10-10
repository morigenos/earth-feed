app.directive('restService', ['FilterMetadataService', function() {
	return {
		restrict: 'E',
		templateUrl: 'resources/app/modules/downloadsRestServices/restService.html',
		scope: {
			'restService': '='
		},
		controller: function($scope, FilterMetadataService) {
			$scope.urlSedeAplicaciones = "";
			
			FilterMetadataService.getUrlSedeAplicaciones()
				.success(function(data) {
					$scope.urlSedeAplicaciones = data.urlSedeAplicaciones;
				})
				.error(function(data, status) {
					$scope.urlSedeAplicaciones = "";
					console.error('Error al recuperar la url de sede aplicaciones.');
				});
		}
	};
}]);