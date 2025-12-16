<?php
	function get_error_login(){
		$mensaje = "<script type='text/javascript'> 
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido iniciar sesión con éxito, por favor revisa todos los datos e inténtelo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
            		</script>";
		return $mensaje;
	}

	function get_success_login(){
		$mensaje = "<script>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'Ha iniciado sesión con éxito, no olvide cerrar sesión cuando termine su trabajo.',
                                type: 'success',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                    </script>";
        return $mensaje;
	}

	function get_error_insert_user(){
		$mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido agregar al usuario con éxito, por favor revisa todos los datos e inténtelo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                        
                    </script>";
		return $mensaje;
	}

	function get_success_insert_user(){
		$mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'Se ha agregado al usuario con éxito. <br> Si desea agregar un nuevo usuario presione el botón Agregar.',
                                type: 'success',
                                
                                animation: 'show',
                                confirm: {
                                    confirm: true,
                                    buttons: [{
                                            text: 'Agregar',
                                            addClass: 'btn btn-success',
                                            click: function(notice) {
                                                notice.remove();
                                                document.location='agregarUsuario';
                                            }
                                        }, {
                                            text: 'Volver',
                                            click: function(notice) {
                                                notice.remove();
                                                document.location='perfil';
                                            }
                                        }]
                                }   
                            });
                        });
                    </script>";
		return $mensaje;
	}

    function get_success_delete_user($cedulaUsuario){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'El usuario con cédula No: ".$cedulaUsuario." ha sido eliminado con éxito. <br> La lista de usuarios será acutalizada al cerrar está notificación.',
                                type: 'success',
                                hide: false,
                                animation: 'show',
                                before_close: function() {
                                    document.location='listarUsuarios';
                                }
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_error_delete_user(){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido eliminar al usuario con éxito, porfavor recarga la página e inténtalo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_confirm_delete_user(){
        $mensaje = "<script type='text/javascript'>
                    function eliminarUsuario(cedulaUsuario){
                        new PNotify({
                            title: '¿Eliminar Usuario?',
                            text: '¿Está seguro que desea eliminar el usuario: '+cedulaUsuario+'?',
                            icon: 'glyphicon glyphicon-question-sign',
                            hide: false,
                            animation: 'show',
                            confirm: {
                                confirm: true,
                                buttons: [{
                                            text: 'Eliminar',
                                            addClass: 'btn btn-danger',
                                            click: function(notice) {
                                                notice.remove();
                                                var url = '../controller/eliminarUsuarioAjax'; 
                                                var parametros = { 
                                                    'cedulaUsuario' : cedulaUsuario,
                                                };
                                                $.ajax({
                                                   type: 'POST',
                                                   url: url,
                                                   data: parametros,
                                                   success: function(data)
                                                   {
                                                       $('#mensaje').html(data); // Mostrar la respuesta del script PHP.
                                                   }
                                                });
                                            }
                                        }, {
                                            text: 'Cancelar',
                                            click: function(notice) {
                                                notice.remove();
                                            }
                                        }]
                            },
                            buttons: {
                                closer: false,
                                sticker: false,
                            },
                            history: {
                                history: false
                            }
                        })
                    }
                </script>";
        return $mensaje;
    }

    function get_script_edit_user(){
        $mensaje = "<script type='text/javascript'>
                        $('.open').click(function(){
                            $('#e_nombre').html(''); // limpio los campos de los errores.
                            $('#e_apellido').html('');
                            $('#e_cedula').html('');
                            $('#e_password').html('');
                            $('#e_repetir_password').html('');
                            var cedula = $(this).data('id');
                            var parametros = {
                                'cedula' : cedula,
                            };
                            var url = '../controller/editarUsuarioAjax'; // El script a dónde se realizará la petición.
                            $.ajax({
                               type: 'POST',
                               url: url,
                               data: parametros, // Adjuntar los campos a enviar
                               success: function(data)
                               {
                                   $('#mensaje').html(data); // Mostrar la respuestas del script PHP.
                               }
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_success_edit_user($cedula){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'Se ha editado al usuario: ".$cedula." con éxito. <br>La página será recargada en 7 segundos.',
                                type: 'success',
                                delay: 6500,
                                animation: 'show',
                            });
                        });

                    setTimeout(function(){
                        location.reload();
                    }, 7000);
                </script>";
        return $mensaje;
    }

    function get_error_edit_user(){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido editar al usuario con éxito, por favor revisa todos los datos e inténtelo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_success_edit_empresa($texto){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'La ".$texto." de la empresa se ha guardado exitosamente.',
                                type: 'success',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_error_edit_empresa($texto){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido guardar la ".$texto." de la empresa con éxito, por favor revisa todos los datos e inténtelo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_success_send_email(){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'El mensaje ha sido enviado con éxito, pronto nos contactáremos con usted.<br> Gracias por escribirnos...',
                                type: 'success',
                                delay: 6000,
                                animation: 'show',
                                before_close: function() {
                                    location.reload();
                                }
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_error_send_email(){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido enviar la información con éxito, por favor revisa todos los datos e inténtelo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                    </script>";
        return $mensaje;
    }


    function get_confirm_delete_project(){
        $mensaje = "<script type='text/javascript'>
                    function eliminarProyecto(idProyecto,nombreProyecto){
                        new PNotify({
                            title: '¿Eliminar Proyecto?',
                            text: '¿Está seguro que desea eliminar el proyecto: '+nombreProyecto+'?<br>Recuerde que se eliminarán todas las imágenes relacionadas con el proyecto.',
                            icon: 'glyphicon glyphicon-question-sign',
                            hide: false,
                            animation: 'show',
                            confirm: {
                                confirm: true,
                                buttons: [{
                                            text: 'Eliminar',
                                            addClass: 'btn btn-danger',
                                            click: function(notice) {
                                                notice.remove();
                                                var url = '../controller/eliminarProyectoAjax'; 
                                                var parametros = { 
                                                    'idProyecto' : idProyecto,
                                                };
                                                $.ajax({
                                                   type: 'POST',
                                                   url: url,
                                                   data: parametros,
                                                   success: function(data)
                                                   {
                                                       $('#mensaje').html(data); // Mostrar la respuesta del script PHP.
                                                   }
                                                });
                                            }
                                        }, {
                                            text: 'Cancelar',
                                            click: function(notice) {
                                                notice.remove();
                                            }
                                        }]
                            },
                            buttons: {
                                closer: false,
                                sticker: false,
                            },
                            history: {
                                history: false
                            }
                        })
                    }
                </script>";
        return $mensaje;
    }

    function get_success_delete_project($nombreProyecto){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'El proyecto: ".$nombreProyecto." ha sido eliminado con éxito. <br> La lista de proyectos será acutalizada al cerrar está notificación.',
                                type: 'success',
                                hide: false,
                                animation: 'show',
                                before_close: function() {
                                    document.location='listarProyectos';
                                }
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_error_delete_project(){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido eliminar el proyecto con éxito, porfavor recarga la página e inténtalo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_confirm_delete_service(){
        $mensaje = "<script type='text/javascript'>
                    function eliminarServicio(idServicio,nombreServicio){
                        new PNotify({
                            title: '¿Eliminar Servicio?',
                            text: '¿Está seguro que desea eliminar el servicio: '+nombreServicio+'?<br>Recuerde que se eliminarán todas las imágenes relacionadas con el servicio.',
                            icon: 'glyphicon glyphicon-question-sign',
                            hide: false,
                            animation: 'show',
                            confirm: {
                                confirm: true,
                                buttons: [{
                                            text: 'Eliminar',
                                            addClass: 'btn btn-danger',
                                            click: function(notice) {
                                                notice.remove();
                                                var url = '../controller/eliminarServicioAjax'; 
                                                var parametros = { 
                                                    'idServicio' : idServicio,
                                                };
                                                $.ajax({
                                                   type: 'POST',
                                                   url: url,
                                                   data: parametros,
                                                   success: function(data)
                                                   {
                                                       $('#mensaje').html(data); // Mostrar la respuesta del script PHP.
                                                   }
                                                });
                                            }
                                        }, {
                                            text: 'Cancelar',
                                            click: function(notice) {
                                                notice.remove();
                                            }
                                        }]
                            },
                            buttons: {
                                closer: false,
                                sticker: false,
                            },
                            history: {
                                history: false
                            }
                        })
                    }
                </script>";
        return $mensaje;
    }

    function get_success_delete_service($nombreServicio){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'El servicio: ".$nombreServicio." ha sido eliminado con éxito. <br> La lista de servicios será acutalizada al cerrar está notificación.',
                                type: 'success',
                                hide: false,
                                animation: 'show',
                                before_close: function() {
                                    document.location='listarServicios';
                                }
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_error_delete_service(){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido eliminar el servicio con éxito, porfavor recarga la página e inténtalo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_confirm_delete_client(){
        $mensaje = "<script type='text/javascript'>
                    function eliminarCliente(idCliente,nombreCliente){
                        new PNotify({
                            title: '¿Eliminar Cliente?',
                            text: '¿Está seguro que desea eliminar el cliente: '+nombreCliente+'?',
                            icon: 'glyphicon glyphicon-question-sign',
                            hide: false,
                            animation: 'show',
                            confirm: {
                                confirm: true,
                                buttons: [{
                                            text: 'Eliminar',
                                            addClass: 'btn btn-danger',
                                            click: function(notice) {
                                                notice.remove();
                                                var url = '../controller/eliminarClienteAjax'; 
                                                var parametros = { 
                                                    'idCliente' : idCliente,
                                                };
                                                $.ajax({
                                                   type: 'POST',
                                                   url: url,
                                                   data: parametros,
                                                   success: function(data)
                                                   {
                                                       $('#mensaje').html(data); // Mostrar la respuesta del script PHP.
                                                   }
                                                });
                                            }
                                        }, {
                                            text: 'Cancelar',
                                            click: function(notice) {
                                                notice.remove();
                                            }
                                        }]
                            },
                            buttons: {
                                closer: false,
                                sticker: false,
                            },
                            history: {
                                history: false
                            }
                        })
                    }
                </script>";
        return $mensaje;
    }

    function get_success_delete_client($nombreCliente){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'El cliente: ".$nombreCliente." ha sido eliminado con éxito. <br> La lista de clientes será acutalizada al cerrar está notificación.',
                                type: 'success',
                                hide: false,
                                animation: 'show',
                                before_close: function() {
                                    document.location='listarClientes';
                                }
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_error_delete_client(){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido eliminar el cliente con éxito, porfavor recarga la página e inténtalo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_confirm_delete_image_slider(){
        $mensaje = "<script type='text/javascript'>
                    function eliminarImagen(idImagen, tituloImagen){
                        new PNotify({
                            title: '¿Eliminar Imagen del Slider?',
                            text: '¿Está seguro que desea eliminar la imagen con titulo: '+tituloImagen+'?',
                            icon: 'glyphicon glyphicon-question-sign',
                            hide: false,
                            animation: 'show',
                            confirm: {
                                confirm: true,
                                buttons: [{
                                            text: 'Eliminar',
                                            addClass: 'btn btn-danger',
                                            click: function(notice) {
                                                notice.remove();
                                                var url = '../controller/eliminarSliderAjax'; 
                                                var parametros = { 
                                                    'idImagen' : idImagen,
                                                };
                                                $.ajax({
                                                   type: 'POST',
                                                   url: url,
                                                   data: parametros,
                                                   success: function(data)
                                                   {
                                                       $('#mensaje').html(data); // Mostrar la respuesta del script PHP.
                                                   }
                                                });
                                            }
                                        }, {
                                            text: 'Cancelar',
                                            click: function(notice) {
                                                notice.remove();
                                            }
                                        }]
                            },
                            buttons: {
                                closer: false,
                                sticker: false,
                            },
                            history: {
                                history: false
                            }
                        })
                    }
                </script>";
        return $mensaje;
    }

    function get_script_edit_image_slider(){
        $mensaje = "<script type='text/javascript'>
                        $('.open').click(function(){
                            var id = $(this).data('id');
                            var parametros = {
                                'idImagen' : id,
                            };
                            var url = '../controller/editarSliderAjax'; // El script a dónde se realizará la petición.
                            $.ajax({
                               type: 'POST',
                               url: url,
                               data: parametros, // Adjuntar los campos a enviar
                               success: function(data)
                               {
                                   $('#mensaje').html(data); // Mostrar la respuestas del script PHP.
                               }
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_success_edit_image_slider(){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'La imagen se ha editado con éxito.<br>La página será recargada en 7 segundos.',
                                type: 'success',
                                delay: 6500,
                                animation: 'show',
                            });
                        });

                    setTimeout(function(){
                        location.reload();
                    }, 7000);
                </script>";
        return $mensaje;
    }

    function get_error_edit_image_slider(){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido editar la imagen con éxito, porfavor recarga la página e inténtalo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_success_insert_image_slider($nombreArchivo){
       $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'La imagen: ".$nombreArchivo." ha sido agregada con éxito.<br>Si desea agregar una nueva imagen presione el botón Agregar.',
                                type: 'success',
                                animation: 'show',
                                confirm: {
                                    confirm: true,
                                    buttons: [{
                                            text: 'Agregar',
                                            addClass: 'btn btn-success',
                                            click: function(notice) {
                                                notice.remove();
                                                document.location='agregarImagenSlider';
                                            }
                                        }, {
                                            text: 'Volver',
                                            click: function(notice) {
                                                notice.remove();
                                                document.location='perfil';
                                            }
                                        }]
                                }   
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_error_insert_image_slider(){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido agregar la imagen con éxito, por favor revisa todos los datos e inténtelo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                        
                    </script>";
        return $mensaje;
    }

    function get_success_delete_image_slider($tituloImagen){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'La imagen: ".$tituloImagen." se ha eliminado con éxito<br>La lista de imagenes será acutalizada al cerrar está notificación.',
                                type: 'success',
                                hide: false,
                                animation: 'show',
                                before_close: function() {
                                    document.location='listarSlider';
                                }
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_error_delete_image_slider(){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido eliminar la imagen con éxito, porfavor recarga la página e inténtalo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_success_insert_client($nombreCliente){
       $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción Exitosa',
                                text: 'El cliente: ".$nombreCliente." ha sido agregado con éxito.<br>Si desea agregar un nuev cliente presione el botón Agregar.',
                                type: 'success',
                                animation: 'show',
                                confirm: {
                                    confirm: true,
                                    buttons: [{
                                            text: 'Agregar',
                                            addClass: 'btn btn-success',
                                            click: function(notice) {
                                                notice.remove();
                                                document.location='agregarCliente';
                                            }
                                        }, {
                                            text: 'Volver',
                                            click: function(notice) {
                                                notice.remove();
                                                document.location='perfil';
                                            }
                                        }]
                                }   
                            });
                        });
                    </script>";
        return $mensaje;
    }

    function get_error_insert_client(){
        $mensaje = "<script type='text/javascript'>
                        $(function(){
                            new PNotify({
                                title: 'Acción No Exitosa :(',
                                text: 'No se ha podido agregar el cliente con éxito, por favor revisa todos los datos e inténtelo de nuevo.',
                                type: 'error',
                                delay: 6000,
                                animation: 'show',
                            });
                        });
                        
                    </script>";
        return $mensaje;
    }

?>