<?php 
	session_start();
	if(!isset($_SESSION['idUsuario'],$_SESSION['nombreUsuario'], $_SESSION['apellidoUsuario'], $_SESSION['superAdminUsuario'])){
		header('location: error');
	}
		include_once ("imports.php");
		include_once ("header.php");
		include_once ("nav.php");
		include_once ("footer.php"); 
		require_once ("../controller/notificaciones.php");
		require_once ("../controller/userModel.php");
		require_once ("../controller/empresaModel.php");
		getImportsUp();
		$nombre = $_SESSION['nombreUsuario'];
		$apellido = $_SESSION['apellidoUsuario'];
		if($_SESSION['primer_inicio'] == 1){
			$_SESSION['primer_inicio'] = null;
			echo get_success_login();
		}
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
					?>
			</div>
			<div class="contenido">
				<div class="row">
					<div class="col-xs-12 col-sm-12 col-md-12">
						<h3 class="h3 center" style="color: #000; margin-bottom: 30px;" >
							¡Bienvenido <?php echo $nombre." ".$apellido ?>! <br> Aquí puede administrar el sitio web de Ingnovarq S.A.S
						</h3>
					</div>
				</div>
				<div class="row">
					<?php 
						if($_SESSION['superAdminUsuario'] == 1){
					?>
					<div class="col-xs-12 col-sm-12 col-md-6">
						<div class="panel panel-default administrador">
							<div class="panel-heading col-xs-12 col-sm-12 col-md-12">
								<div class="title-admin col-md-10 col-xs-12 col-sm-12">
									<h2 style="color: white;">Gestión de Usuarios</h2>
								</div>
								<div class="col-md-2 admin-img">
									<a>
										<img src="../../images/administrador/user.png" class="img-responsive">
									</a>
								</div>
							</div>
							<div class="panel-body col-xs-12 col-sm-12 col-md-12 color-content-admin">
								<div class="col-md-6 col-xs-6 col-sm-6">
									<a href="agregarUsuario">
										<img src="../../images/administrador/add.png" class="img-responsive">
									</a>
								</div>
								<div class="col-md-6 col-xs-6 col-sm-6">
									<a href="listarUsuarios">
										<img src="../../images/administrador/search.png" class="img-responsive">
									</a>
								</div>
							</div>
						</div>
					</div>
					<?php } ?>
					<div class="col-xs-12 col-sm-12 col-md-6">
						<div class="panel panel-default administrador">
							<div class="panel-heading col-xs-12 col-sm-12 col-md-12">
								<div class="title-admin col-md-10 col-xs-12 col-sm-12">
									<h2 style="color: white;">Gestión de Clientes</h2>
								</div>
								<div class="col-md-2 admin-img">
									<a>
										<img src="../../images/administrador/users.png" class="img-responsive">
									</a>
								</div>
							</div>
							<div class="panel-body col-xs-12 col-sm-12 col-md-12 color-content-admin">
								<div class="col-md-6 col-xs-6 col-sm-6">
									<a href="agregarCliente">
										<img src="../../images/administrador/add.png" class="img-responsive">
									</a>
								</div>
								<div class="col-md-6 col-xs-6 col-sm-6">
									<a href="listarClientes">
										<img src="../../images/administrador/search.png" class="img-responsive">
									</a>
								</div>
							</div>
						</div>
					</div>
					<div class="col-xs-12 col-sm-12 col-md-6">
						<div class="panel panel-default administrador">
							<div class="panel-heading col-xs-12 col-sm-12 col-md-12">
								<div class="title-admin col-md-10 col-xs-12 col-sm-12">
									<h2 style="color: white;">Gestión de Proyectos</h2>
								</div>
								<div class="col-md-2 admin-img">
									<a>
										<img src="../../images/administrador/projects.png" class="img-responsive">
									</a>
								</div>
							</div>
							<div class="panel-body col-xs-12 col-sm-12 col-md-12 color-content-admin">
								<div class="col-md-6 col-xs-6 col-sm-6">
									<a href="agregarProyecto">
										<img src="../../images/administrador/add.png" class="img-responsive">
									</a>
								</div>
								<div class="col-md-6 col-xs-6 col-sm-6">
									<a href="listarProyectos">
										<img src="../../images/administrador/search.png" class="img-responsive">
									</a>
								</div>
							</div>
						</div>
					</div>
					<?php 
						if($_SESSION['superAdminUsuario'] == 1){
					?>
					<div class="col-xs-12 col-sm-12 col-md-6">
						<div class="panel panel-default administrador">
							<div class="panel-heading col-xs-12 col-sm-12 col-md-12">
								<div class="title-admin col-md-10 col-xs-12 col-sm-12">
									<h2 style="color: white;">Gestión de Servicios</h2>
								</div>
								<div class="col-md-2 admin-img">
									<a>
										<img src="../../images/administrador/services.png" class="img-responsive">
									</a>
								</div>
							</div>
							<div class="panel-body col-xs-12 col-sm-12 col-md-12 color-content-admin">
								<div class="col-md-6 col-xs-6 col-sm-6">
									<a href="inicio">
										<img src="../../images/administrador/add.png" class="img-responsive">
									</a>
								</div>
								<div class="col-md-6 col-xs-6 col-sm-6">
									<a href="listarServicios">
										<img src="../../images/administrador/search.png" class="img-responsive">
									</a>
								</div>
							</div>
						</div>
					</div>
					<?php } ?>
					<div class="col-xs-12 col-sm-12 col-md-6">
						<div class="panel panel-default administrador">
							<div class="panel-heading col-xs-12 col-sm-12 col-md-12">
								<div class="title-admin col-md-10 col-xs-12 col-sm-12">
									<h2 style="color: white;">Gestión de Empresa</h2>
								</div>
								<div class="col-md-2 admin-img">
									<a>
										<img src="../../images/administrador/user.png" class="img-responsive">
									</a>
								</div>
							</div>
							<div class="panel-body col-xs-12 col-sm-12 col-md-12 color-content-admin">
								<div class="col-md-4 col-xs-4 col-sm-4">
									<a href="#sinAccion" data-toggle="modal" data-target="#mision" title="Misión Empresarial">
										<div><img src="../../images/administrador/mision.png" class="img-responsive"></div>
									</a>
								</div>
								<div class="col-md-4 col-xs-4 col-sm-4">
									<a href="#sinAccion" data-toggle="modal" data-target="#vision" title="Visión Empresarial">
										<div><img src="../../images/administrador/vision.png" class="img-responsive"></div>
									</a>
								</div>
								<div class="col-md-4 col-xs-4 col-sm-4">
									<a href="#sinAccion" data-toggle="modal" data-target="#filosofia" title="Filosofía Empresarial">
										<div><img src="../../images/administrador/valores.png" class="img-responsive"></div>
									</a>
								</div>
							</div>
						</div>
					</div>
					<div class="col-xs-12 col-sm-12 col-md-6">
						<div class="panel panel-default administrador">
							<div class="panel-heading col-xs-12 col-sm-12 col-md-12">
								<div class="title-admin col-md-10 col-xs-12 col-sm-12">
									<h2 style="color: white;">Gestión del Slider</h2>
								</div>
								<div class="col-md-2 admin-img">
									<a>
										<img src="../../images/administrador/slider.png" class="img-responsive">
									</a>
								</div>
							</div>
							<div class="panel-body col-xs-12 col-sm-12 col-md-12 color-content-admin">
								<div class="col-md-6 col-xs-6 col-sm-6">
									<a href="agregarImagenSlider">
										<img src="../../images/administrador/add.png" class="img-responsive">
									</a>
								</div>
								<div class="col-md-6 col-xs-6 col-sm-6">
									<a href="listarSlider">
										<img src="../../images/administrador/search.png" class="img-responsive">
									</a>
								</div>
							</div>
						</div>
					</div>
				</div>

				<?php 
		         	$empresaModel = new EmpresaModel();
		         	$mision = $empresaModel->get_mision();
		         	$vision = $empresaModel->get_vision();
		         	$filosofia = $empresaModel->get_filosofia();

		         	$mision = str_replace("<br />","\n", $mision['misionEmpresa']);
		         	$vision = str_replace("<br />","\n", $vision['visionEmpresa']);
		         	$filosofia = str_replace("<br />","\n", $filosofia['filosofiaEmpresa']);
		        ?>
					<!-- Ventana Modal para la misión empresarial -->
					<div class="modal fade" id="mision" tabindex="-1" role="dialog" aria-labelledby="myModalLabel" aria-hidden="true">
					  <div class="modal-dialog">
					    <div class="modal-content">

					      <div class="modal-header">
					        <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
					        <h3 class="modal-title" id="myModalLabel">Misión Empresarial</h3> 
					      </div>

					      <div class="modal-body">
					    	<div id="mensajeMision"></div>
					      	<form class="form-horizontal" id="form-editar-mision-ajax" method="post">
							     <div class="form-group">
							         <label for="mision" class="control-label col-xs-2">Misión:</label>
							         <div class="col-xs-10">
							            <textarea id="mision" name="mision" class="form-control" rows="19"><?php echo $mision; ?></textarea>
							         	<div class="col-xs-10 error-text" id="e_mision"></div>
							         </div>
							     </div>
								     
							     <div class="form-group">
							        <div class="col-xs-offset-2 col-xs-10">
							         	<input type="hidden" name="ajaxMision">
							         	<button type="submit" id="btn-editar-mision-ajax" class="btn btn-success">
							            	<span class="glyphicon glyphicon-ok" aria-hidden="true"></span> Guardar Cambios
							            </button>
							        </div>
							     </div>
							</form>   	 
					      </div>

					      <div class="modal-footer">
					        <button type="button" id="cerrar" class="btn btn-default" data-dismiss="modal">Cerrar</button>   
					      </div>
					    </div>
					  </div>
					</div> <!-- /- Cierro la ventana Modal para la misión empresarial-->

					<!-- Ventana Modal para la visión empresarial -->
					<div class="modal fade" id="vision" tabindex="-1" role="dialog" aria-labelledby="myModalLabel" aria-hidden="true">
					  <div class="modal-dialog">
					    <div class="modal-content">

					      <div class="modal-header">
					        <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
					        <h3 class="modal-title" id="myModalLabel">Visión Empresarial</h3> 
					      </div>

					      <div class="modal-body">
					    	<div id="mensajeVision"></div>
					      	<form class="form-horizontal" id="form-editar-vision-ajax" method="post">
							     <div class="form-group">
							         <label for="" class="control-label col-xs-2">Visión:</label>
							         <div class="col-xs-10">
							            <textarea id="vision" name="vision" class="form-control" rows="19"><?php echo $vision; ?></textarea>
							         	<div class="col-xs-10 error-text" id="e_vision"></div>
							         </div>
							     </div>
								     
							     <div class="form-group">
							        <div class="col-xs-offset-2 col-xs-10">
							         	<input type="hidden" name="ajaxVision">
							         	<button type="submit" id="btn-editar-vision-ajax" class="btn btn-success">
							            	<span class="glyphicon glyphicon-ok" aria-hidden="true"></span> Guardar Cambios
							            </button>
							        </div>
							     </div>
							</form>
					      </div>

					      <div class="modal-footer">
					        <button type="button" id="cerrar" class="btn btn-default" data-dismiss="modal">Cerrar</button>   
					      </div>
					    </div>
					  </div>
					</div> <!-- /- Cierro la ventana Modal para la visión empresarial-->

					<!-- Ventana Modal para la filosofía empresarial -->
					<div class="modal fade" id="filosofia" tabindex="-1" role="dialog" aria-labelledby="myModalLabel" aria-hidden="true">
					  <div class="modal-dialog">
					    <div class="modal-content">

					      <div class="modal-header">
					        <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
					        <h3 class="modal-title" id="myModalLabel">Filosofía Empresarial</h3> 
					      </div>

					      <div class="modal-body">
					    	<div id="mensajeFilosofia"></div>
					      	<form class="form-horizontal" id="form-editar-filosofia-ajax" method="post">
							     <div class="form-group">
							         <label for="" class="control-label col-xs-2">Filosofía:</label>
							         <div class="col-xs-10">
							            <textarea id="filosofia" name="filosofia" class="form-control" rows="19"><?php echo $filosofia; ?></textarea>
							         	<div class="col-xs-10 error-text" id="e_filosofia"></div>
							         </div>
							     </div>
								     
							     <div class="form-group">
							        <div class="col-xs-offset-2 col-xs-10">
							         	<input type="hidden" name="ajaxFilosofia">
							         	<button type="submit" id="btn-editar-filosofia-ajax" class="btn btn-success">
							            	<span class="glyphicon glyphicon-ok" aria-hidden="true"></span> Guardar Cambios
							            </button>
							        </div>
							     </div>
							</form>
					      </div>

					      <div class="modal-footer">
					        <button type="button" id="cerrar" class="btn btn-default" data-dismiss="modal">Cerrar</button>   
					      </div>
					    </div>
					  </div>
					</div> <!-- /- Cierro la ventana Modal para la filosofía empresarial-->
			</div>
		</div>
		<?php
			getFooter(); 
			getImportsDown();
		?>