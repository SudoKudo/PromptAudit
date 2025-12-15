<?php 
	function getNav(){
		?>

		<nav class="clearfix paralelogramo">
			<ul class="clearfix">
				<li class="cuadrado">
					<a href="inicio" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'inicio')){
						echo 'seleccionado';
					}?>">Inicio</a>
				</li>
				<li class="cuadrado">
					<a href="nosotros" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'nosotros')){
						echo 'seleccionado';
					}?>">Nosotros</a>
				</li>
				<li class="cuadrado" >
					<a href="servicios" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'servicios')){
						echo 'seleccionado';
					}?>">Servicios</a>
				</li>
				<li class="cuadrado" >
					<a href="proyectos" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'proyectos')){
						echo 'seleccionado';
					}?>">Proyectos</a>
				</li>
				<li class="cuadrado" >
					<a href="contacto" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'contacto')){
						echo 'seleccionado';
					}?>">Contáctenos</a>
				</li>	
			</ul>
			<a href="#" id="pull">Menú</a>
		</nav>

		<?php
	}

	function getNavSuperAdmin(){
		?>

		<nav class="clearfix paralelogramo">
			<ul class="clearfix">
				<li class="cuadrado">
					<a href="perfil" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'perfil')){
						echo 'seleccionado';
					}?>">Inicio</a>
				</li>
				<li class="cuadrado">
					<a href="agregarUsuario" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'agregarUsuario')){
						echo 'seleccionado';
					}?>">Crear usuario</a>
				</li>
				<li class="cuadrado" >
					<a href="agregarServicio" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'agregarServicio')){
						echo 'seleccionado';
					}?>">Crear servicio</a>
				</li>
				<li class="cuadrado" >
					<a href="agregarProyecto" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'agregarProyecto')){
						echo 'seleccionado';
					}?>">Crear proyecto</a>
				</li>
				<li class="cuadrado" >
					<a href="agregarCliente" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'agregarCliente')){
						echo 'seleccionado';
					}?>">Crear cliente</a>
				</li>
				<li class="cuadrado" >
					<a href="agregarImagenSlider" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'agregarImagenSlider')){
						echo 'seleccionado';
					}?>">Crear imagen del slider</a>
				</li>
				<li class="cuadrado" >
					<a href="../controller/logout" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'agregarCliente')){
						echo 'seleccionado';
					}?>">Cerrar Sesión</a>
				</li>	
			</ul>
			<a href="#" id="pull">Menú</a>
		</nav>

		<?php
	}

	function getNavAdmin(){
		?>

		<nav class="clearfix paralelogramo">
			<ul class="clearfix">
				<li class="cuadrado">
					<a href="perfil" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'perfil')){
						echo 'seleccionado';
					}?>">Inicio</a>
				</li>
				<li class="cuadrado" >
					<a href="agregarServicio" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'agregarServicio')){
						echo 'seleccionado';
					}?>">Crear servicio</a>
				</li>
				<li class="cuadrado" >
					<a href="agregarProyecto" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'agregarProyecto')){
						echo 'seleccionado';
					}?>">Crear proyecto</a>
				</li>
				<li class="cuadrado" >
					<a href="agregarCliente" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'agregarCliente')){
						echo 'seleccionado';
					}?>">Crear cliente</a>
				</li>
				<li class="cuadrado" >
					<a href="agregarImagenSlider" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'agregarImagenSlider')){
						echo 'seleccionado';
					}?>">Crear imagen del slider</a>
				</li>
				<li class="cuadrado" >
					<a href="../controller/logout" id="<?php if(strstr($_SERVER['REQUEST_URI'], 'agregarCliente')){
						echo 'seleccionado';
					}?>">Cerrar Sesión</a>
				</li>	
			</ul>
			<a href="#" id="pull">Menú</a>
		</nav>

		<?php
	}
?>