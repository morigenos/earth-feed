app.service('DownloadsService', function($http) {
	
	this.getDownloads = function () {
		return $http.get("./resources/app/modules/downloads/downloads.json");
	};
	
	this.getProducers = function () {
		return $http.get("./resources/app/modules/downloads/producers.json");
	}
	
	this.getStationTypes = function () {
		return $http.get("./resources/app/modules/downloads/stationTypes.json");
	}
	
	this.getExtensiones = function () {
		return $http.get("rest/extensiones");
	}
	
	this.getPathFileExcelEstaciones = function () {
		return $http.get("rest/pathReportEESS");
	}
	
	this.getPathFileExcelEmbarcaciones = function () {
		return $http.get("rest/pathReportEmbarcaciones");
	}
	
	this.downloadPlanesValidosOperadores = function (extension) {
		return $http.get("rest/pathReportPlanesValidosOperadores", {
			params: {
				extension: extension
			}
		});
	}
	
	this.getPathFilePreciosPorCarburante = function (tipoEstacion, productoId, tipoRangoId) {
		return $http.get("rest/pathReportPreciosPorCarburante", {
			params: {
				tipoEstacion: tipoEstacion,
				productoId: productoId,
				tipoRangoId: tipoRangoId
			}
		});
	}
});