app.controller('DownloadsCtrl', [ '$scope', '$animate', 'DownloadsService','$filter','FilterMetadataService',
	function($scope, $animate, DownloadsService, $filter, FilterMetadataService) {		
		/**
		 * List of downloads.
		 */
		$scope.downloads = [];
		
		/**
		 * It's the id of the download type that is showing its panel.
		 */
		$scope.panelShowedId = null;


		/**
		 * List of restServices
		 */
		$scope.listaRest = [];
		
		
		$scope.urlSedeAplicaciones = "";
		
		FilterMetadataService.getUrlSedeAplicaciones()
			.success(function(data) {
				$scope.urlSedeAplicaciones = data.urlSedeAplicaciones;
			})
			.error(function(data, status) {
				$scope.urlSedeAplicaciones = "";
				console.error('Error al recuperar la url de sede aplicaciones.');
			});
		
		/**
		 * Obtains the list of downloads from the service.
		 */
		DownloadsService.getDownloads()
			.success(function(data) {
				$scope.downloads = data;				
				var rest=data[3].restServices;				
				$scope.listaRest=rest;				
			})
			.error(function(data, status) {
				$scope.downloads = [];
				console.error('Error');
			});
		
		$scope.isPanelShowed = function(idDownloadType) {
			return $scope.panelShowedId != null && $scope.panelShowedId === idDownloadType;
		}
		
		$scope.togglePanel = function(idDownloadType) {
			if ($scope.isPanelShowed(idDownloadType)) {
				$scope.panelShowedId = null;
			} else {
				changeStyleAfterIconPanel("icon_" + idDownloadType, "desplegable_" + idDownloadType);
				$scope.panelShowedId = idDownloadType;
			}
		};
	} 
]);