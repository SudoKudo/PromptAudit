<?php
session_start();
?>
<html lang="en" class="no-js">
	<head>
		<title>TekNet Login</title>
		<meta name="description" content=TekNet Login  " />
		<link rel="shortcut icon" href="../favicon.ico"> 
		<link rel="stylesheet" type="text/css" href="css/default.css" />
		<link rel="stylesheet" type="text/css" href="css/component.css" />
		<link rel="stylesheet" type="text/css" href="css/menu.css"> 
	</head>
	<body>
		<div class="container">
			<!-- Top Navigation -->

			<header>
<a href="index.php"><img src="images/theteknet.png"></a>
			<div class="clear"></div>
				<h1>Login <span>Welcome back, please login</h1>	
			</header>
			<section class="color-1">
				<p class="text note-touch">Please enter your email and password. <br>To try out this site as a demo user, please login as email: jsmith@palo-alto.edu, password: demouser</p>
				<p>
				<form action method="post">
				Email: <input type="text" name="email" placeholder="john.s.48821@palo-alto.edu">
				<br>
				<br>
				Password: <input type="password" name="password" placeholder="*********">
				<br>
				<br>
				<input type="submit" button class="btn btn-1 btn-1a" value="Log in">
				</form>
				<?php
				$email = $_POST["email"];
				$password = $_POST["password"];
				include 'backendstuff/phplogin.php';
                $con=new mysqli($host,$user,$pwd,$db);               
$result = mysqli_query($con, "SELECT * FROM registeredusers WHERE email='$email'");
while($row = mysqli_fetch_array($result)) {
  $accountemail=$row['email'];
  $accountpassword=$row['password'];

  }
    if( $email != $accountemail || $password != $accountpassword ){
  echo "Please check your email and password and login again";
}
elseif($email==$accountemail && $password==$accountpassword && $accountpassword!=null){
$_SESSION['sessionemail'] = $email; 
header( 'Location: pages/loggedin.php' ) ;

}
mysqli_close($con);
				?>
				
</section>
<font color=teal><?php include 'version.php'?></font>