
<html lang="en" class="no-js">
	<head>
<title>TekNet - Home</title>

</head>

			<?php
include '../includeme.php';
include '../getelement.php';
include '../backendstuff/phplogin.php';

?>

<header>
	<center><img src="../images/theteknet.png"></center>
				<?php 
				echo "<h1>TekNet - Home  </h1> <span>Welcome back, $email </span>";
				?>
			</header>
			<section class="color-1">
			<form method = "post">
			Sooo, what have you been up to lately?
			<br>
			<form method="get">
			<input type="text" name="status" placeholder="..." style="width:700px">
			<input type="submit" button class="btn btn-1 btn-1a" value="Share" style="width:10px">
			</form>
			
			
    <br>
</head>
<?php
$result=$con->query("SELECT name FROM registeredusers WHERE email='$email'");
$name=$result->fetch_row();
$_SESSION['name'] = $name[0];

$namestatus=$con->query("SELECT name,message,postnum FROM status ORDER BY postnum");
$statusentery = $_POST[status];
$position = strpos($statusentery,"<");
if ($position === 0){
	echo "Sorry, for security purposes we do not allow characters such as <";
	exit;
}
if ($statusentery != null){
if ($con->query("INSERT INTO status(message, name, date, postnum) VALUES('$statusentery', '$name[0]', now(), 2)") === TRUE) {
    echo "<script>document.location.href='http://www.theteknet.com'</script>";
}
else {
    echo "Error: " . $sql . "<br>" . $con->error;
}
}
else{
    echo "Post something";
}
?>
<body>
Latest buzz:
<br>
<h1>
<?php

echo "<br>";
$x=40;
$y=1;

while($x>$y){
    $x = $x-1;

$names=$namestatus->fetch_row();
if ($names[0]==null){
    break;
}
else{
echo $names[0], ": ";
echo $names[1];
echo "<br>";
}
}
echo $name[0];


?>
<br>
</body>