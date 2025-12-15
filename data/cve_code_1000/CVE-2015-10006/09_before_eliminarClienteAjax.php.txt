<?php
    session_start();
     if(!isset($_POST["idCliente"], $_SESSION['idUsuario'],$_SESSION['nombreUsuario'], $_SESSION['apellidoUsuario'], $_SESSION['superAdminUsuario'])){
            header('location: error');
    }
    require_once ("notificaciones.php");
    $mensaje = get_error_delete_client(); // mensaje por defecto de error por si no se cumplen los if

    if(isset($_POST['idCliente'])){
        require_once ("clientModel.php");
        require_once ("imagenModel.php");
        $idCliente = htmlspecialchars($_POST["idCliente"]);
        $imagenModel = new ImagenModel();
        $clientModel = new ClientModel();
        $existente = $clientModel->view_db_client($idCliente); // consulto para saber si existe el cliente

        if($existente != null){ // si existe elimino la imagen asociada y notifico
            $imagenCliente = $imagenModel->view_image_db_client($idCliente);
            if(file_exists($imagenCliente['rutaImagen'])){ //Verifico si existe la imagen
                if(unlink($imagenCliente['rutaImagen'])) { // elimino la imagen
                    $imagenModel->delete_db_image_client($idCliente,$imagenCliente['idImagen']);
                }
            }
            $resultado = $clientModel->delete_db_client($idCliente);
            if($resultado){
                $mensaje =  get_success_delete_client($idCliente); // envio el mensaje alojado en notificaciones
            }
        }
    }

echo $mensaje;
?>