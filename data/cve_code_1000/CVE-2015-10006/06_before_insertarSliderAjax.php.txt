<?php 
    session_start();
    if(!isset($_SESSION['idUsuario'],$_SESSION['nombreUsuario'], $_SESSION['apellidoUsuario'], $_SESSION['superAdminUsuario'])){
            header('location: error');
    }
    require_once ("notificaciones.php");
    require_once ("sliderModel.php");
    $mensaje = get_error_insert_image_slider();
    if(sizeof($_POST) == 1 && isset($_POST['tituloImagen'], $_FILES['myfile'])){
        
        $directorioDeGuardado = "../../images/slide/";
        $nombreArchivo = $_FILES['myfile']['name'];
        $fullPath = $directorioDeGuardado.$nombreArchivo; // construyo la ruta completa donde se guardará el archivo.
        if (! file_exists($fullPath)){ //verifico que no exista la imagen anterior
            $sliderModel = new SliderModel();
            $tituloImagen = $_POST['tituloImagen'];
            move_uploaded_file($_FILES["myfile"]["tmp_name"], $fullPath); //muevo el archivo cargado
            $resultado = $sliderModel->insert_db_image_slider($tituloImagen, $fullPath);
            if($resultado){
                $mensaje = get_success_insert_image_slider($nombreArchivo); // obtengo el mensaje de que todo ha salido bien.
            }
        }
    }
echo $mensaje; 
?>