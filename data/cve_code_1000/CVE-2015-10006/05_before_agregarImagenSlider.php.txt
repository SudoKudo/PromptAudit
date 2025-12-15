<?php 
	session_start();
	if(!isset($_SESSION['idUsuario'],$_SESSION['nombreUsuario'], $_SESSION['apellidoUsuario'], $_SESSION['superAdminUsuario'])){
		header('location: error');
	}
			include_once ("imports.php");
			include_once ("header.php");
			include_once ("nav.php");
			include_once ("footer.php"); 
			require_once "../controller/sliderModel.php";

			getImportsUp();
			$sliderModel = new sliderModel();
			?>

			<body id="body">
				<div class="con" id="con">
					<div class="container" id="main">
							<?php 
								getHeader();
								if($_SESSION['superAdminUsuario'] == 1){
									getNavSuperAdmin();
								}
								else
								getNavAdmin();
								//$direccion = "../controlador/cargarImagenesProductos?idproducto=".$_GET['idproducto'];
							?>
					</div>
					<div class="contenido">
						<div class="row">
							<br>
							<div class="col-xs-12 col-sm-8 col-sm-offset-2 col-md-8 col-md-offset-2">
								<div class="panel panel-default empresa">
									<div class="panel-heading">
										Crear Imagen del Slider.
									</div>
									<div class="panel-body">
										<div id="mensaje"></div>
										<h2 style="color: #019831; text-align: center;">Formulario para agregar una imagen al slider</h2>
										<br>								
										<div class="form-horizontal">
								      		 <input type="hidden" name="idImagen" id="idImagen" readonly="readonly">
										     <div class="form-group">
										         <label for="inputName" class="control-label col-xs-2">Titulo:</label>
										         <div class="col-xs-10">
										            <input type="name" id="tituloImagen" name="tituloImagen" class="form-control" placeholder="Titulo">
										         </div>
										     </div>
										     <div class="form-group">
										     	 <label class="control-label col-xs-2">Imagen:</label>
										         <div class="col-xs-10" id="cargador">
										            <div id="fileuploader">Cargar imagen</div>
										            <p id="nota" class="col-xs-12 text-info">Nota: Si no selecciona ninguna imagen y guarda los cambios, se conservará la imagen actual.
										            </p>
										         </div>
										     </div>    
										     <div class="form-group">
										        <div class="col-xs-offset-2 col-xs-8">
										            <div id="btn-agregar-slider-ajax" class="btn btn-success">
										            	<span class="glyphicon glyphicon-ok" aria-hidden="true"></span> Crear imagen del slider
										            </div> 
										        </div>
										     </div>
										</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
				<?php
					getFooter(); 
					getImportsDown();
?>