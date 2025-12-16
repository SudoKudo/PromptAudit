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
			require_once ("../controller/clientModel.php");
			require_once ("../controller/userModel.php");
			require_once ("../controller/imagenModel.php");
			getImportsUp();
			
			$userModel = new UserModel();
			$clienteModel = new ClientModel();
			$imagenModel = new imagenModel();
			$clientes = $clienteModel->view_all_db_clients();

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
							<br>
							<div class="col-xs-12 col-sm-12 col-md-8 col-md-offset-2">
								<h2 class="text-center">Lista de clientes</h2>
								<br>
								<div class="table-responsive">
									<table  class="table table-bordered table-hover" style="border-radius: 5px; background-color: rgba(129,205,0,0.4);">
										<thead>
											<th>Imagen</th>
											<th>Nombre</th>
											<th>Creado Por</th>
											<th>Editar</th>
											<th>Eliminar</th>
										</thead>
										<tbody>
										<?php
											foreach ($clientes as $fila) {
												?>
											<tr>
												<td>
													<div style="width: 150px; height: 150px;"> <?php $imagenCliente = $imagenModel->view_image_db_client($fila['idCliente']); ?>
														<img class="img-responsive" src="<?php echo $imagenCliente['rutaImagen']; ?>" alt="No posee imagen" title="Imagen representativa del cliente">
													</div> 
												</td>
												<td>
													<?php echo $fila['nombreCliente']; ?>
												</td> 
												<td>
													<?php 
														$usuario = $userModel->view_id_user_db_user($fila['Usuario_idUsuario']);
														echo $usuario['nombreUsuario'];
													?>
												</td>
												<td>
													<a href="#sinAccion" class="open" data-toggle="modal" data-target="#myModal" data-id="" title="Editar cliente">
														<div><img style="width: 50px;" class="img-responsive" src="../../images/administrador/edit.png"/></div>
													</a>	
												</td>	
												<td>
													<a href="#sinAccion" onclick="eliminarCliente(<?php echo $fila['idCliente'] ?>, '<?php echo htmlspecialchars($fila['nombreCliente'], ENT_NOQUOTES); ?>');">
														<div><img style="width: 50px;" class="img-responsive" src="../../images/administrador/delete.png" title="Eliminar cliente"/></div>
													</a>
												</td>						
											</tr>
											<?php
												}
											?>
										</tbody>
									</table>
									<?php	
										echo get_confirm_delete_client(); // imprimo el script para eliminar clientes
									?>
									<div id="mensaje"></div>
								</div>	
							</div>
						</div>
					</div>
				</div> <!-- cierro el container principal-->
				<?php
					getFooter(); 
					getImportsDown();
?>