<?php 
    session_start();
    if(!isset($_SESSION['idUsuario'],$_SESSION['nombreUsuario'], $_SESSION['apellidoUsuario'], $_SESSION['superAdminUsuario'])){
            header('location: error');
    }
    require_once ("notificaciones.php");
    $mensaje = get_error_insert_client();
    print_r($_POST);
    print_r($_FILES);
    if(sizeof($_POST) == 1 && isset($_POST['nombreCliente'], $_FILES['myfile'])){
        
        $directorioDeGuardado = "../../images/clientes/";
        $nombreArchivo = $_FILES['myfile']['name'];
        $fullPath = $directorioDeGuardado.$nombreArchivo; // construyo la ruta completa donde se guardará el archivo.
        if (! file_exists($fullPath)){ //verifico que no exista la imagen anterior
            require_once ("clientModel.php");
            require_once ("userModel.php");
            $clientModel = new ClientModel();
            $userModel = new UserModel();
            $usuario = $userModel->view_db_user($_SESSION['idUsuario']);
            $nombreCliente = htmlspecialchars($_POST['nombreCliente'], ENT_NOQUOTES); //evito ataques XSS
            $resultado = $clientModel->insert_db_client($nombreCliente, $usuario['idUsuario']);
            if($resultado){
                $ultimoCliente = $clientModel->view_db_last_client();
                print_r($ultimoCliente);
                if($ultimoCliente != null){

                    require_once ("imagenModel.php");
                    $imagenModel = new ImagenModel();
                    $resultado = $imagenModel->insert_image_client($fullPath, $nombreCliente, $ultimoCliente['idCliente']);
                    if($resultado){
                        move_uploaded_file($_FILES["myfile"]["tmp_name"], $fullPath); //muevo el archivo cargado
                        $mensaje = get_success_insert_client($nombreCliente); // obtengo el mensaje de que todo ha salido bien.
                    }
                }
                else
                    print("ultimoCliente null");
            }
        }
    }
echo $mensaje; 
?>