<?php 
	/*
	 * Incluyo el modelo.php que contendrá la conexión a la base de datos, y será el padre de esta clase.
	 */
	require_once "model.php";

	class ClientModel extends Model{

		/*
		 * Constructor de la clase ClientModel el cual se conectará a la base de datos por medio del constructor del padre.
		 */
		public function __construct(){
			parent::__construct();
		}

		/*
		 * ------------------------------------------------------------------------------------------------------------
		 * 
		 * ----------------------------------------- CRUD USUARIOS  ---------------------------------------------------
		 * 
		 * ------------------------------------------------------------------------------------------------------------
		 */
		
		/*
		 * Función para insertar un cliente en la base de datos
		 */
		function insert_db_client($nombreCliente, $usuario){

			//Creación de una consulta insertandole parametros para agregar clientes
			$sentencia = $this->_db->prepare("INSERT INTO Cliente (nombreCliente, Usuario_idUsuario) VALUES (:nombre, :usuario)");
			$sentencia->bindParam(':nombre', $nombreCliente);
			$sentencia->bindParam(':usuario', $usuario);

			//Ejecución de la consulta
			return $sentencia->execute();
		}


		/*
		 * Función para eliminar un cliente en la base de datos
		 */
		function delete_db_client($idCliente){

			//Creación de una consulta insertandole parametros para eliminar clientes
			$sentencia = $this->_db->prepare("DELETE FROM Cliente WHERE idCliente = :idCliente");
			$sentencia->bindParam(':idCliente', $idCliente);

			//Ejecución de la consulta
			return $sentencia->execute();
		}

		/*
		 * Función para devolver todos los clientes de la base de datos
		 */
		function view_all_db_clients(){

			$sentencia = $this->_db->prepare("SELECT * FROM Cliente c, Imagen i WHERE i.Cliente_idCliente = c.idCliente");
			$sentencia->execute();
			$response = array();

			while ($fila = $sentencia->fetch()) {
				$response[] = $fila;
			}

			return $response;
		}

		/*
		 * Función para devolver un cliente en especifico de la base de datos
		 */
		function view_db_client($idCliente){

			//Creación de una consulta insertandole parametros para obtener un cliente en especifico
			$sentencia = $this->_db->prepare("SELECT * FROM Cliente where idCliente = :idCliente");
			$sentencia->bindParam(':idCliente', $idCliente);

			$sentencia->execute();
			$response = array();
			while ($fila = $sentencia->fetch()) {
				$response[] = $fila;
			}
			if(sizeof($response) != 0)
				return $cliente = $response[0];
			return null;
		}
	}
?>