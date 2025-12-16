<?php
session_start();
include 'backendstuff/phplogin.php';
$email=$_SESSION[sessionemail];
if($email != null){
    header( 'Location: pages/loggedin.php' ) ;
}
?>

<html lang="en" class="no-js">
	<head>
		<title>TekNet Beta Registration</title>
		<meta name="description" content="TekNet Beta registration" />
		<link rel="shortcut icon" href="../favicon.ico"> 
		<link rel="stylesheet" type="text/css" href="css/default.css" />
		<link rel="stylesheet" type="text/css" href="css/component.css" />
		<link rel="stylesheet" type="text/css" href="css/menu.css">
		<script src="js/modernizr.custom.js"></script>
	</head>
	<body>

		<div class="container">
			<!-- Top Navigation -->
<center><img src="images/Octocat.png" width="30" height="30">Attention: We are now availible on GitHub. Download us at <a href="https://github.com/kirill2485/TekNet">github.com/kirill2485/TekNet</a>.</center>
	<a href="#"><hr></a>
			<header>
					<div class="inner relative">
<div style=height:20px; padding-top:50px;"></div>
			<a id="menu-toggle" class="button dark" href="#""></i></a>
			<nav id="navigation">
				<ul id="main-menu">
					<li class="parent">
						<a href="login.php">Sign in</a>
						<ul class="sub-menu">
							<li><a onclick="prompt("Comming soon")" href="#">Sign up</a></li>
							
						</ul>
					</li>
				</ul>
			</nav>
			<div class="clear"></div>
		</div>
				<h1>TekNet Beta Registration <span> Register to be one of the first beta users on our site</h1>	
			</header>
			<section class="color-1">
				<p class="text note-touch">Sign-ups are currrently closed. You may try using the demo version of the site by clicking "Sign in" at the top right corner, and using the provided demo account. Please enter your email and name to pre-register and receive updates on TekNet's progress.</p>
				<p>
				Please make sure you are over the age of 13, as it would be illegal for us to knowingly collect information from people under the age of 13. Registration is open to PAUSD students only. Scroll down for all of the FAQ's.
				<p>
<form method="get">

    Email:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <input type="text" name="email">
    <br>
    Full name: <input type="text" name="name">
    <br>
    <input type="submit" button class="btn btn-1 btn-1a" value="Submit">
</form >

<?php

$email = $_GET["email"];
$name = $_GET["name"];
$position = strpos($email,"@palo-alto.edu");
if ($position==false && $email!=null){
    echo "<font color='red'>Sorry, you must enter your @palo-alto.edu address to pre-register. To do this, please head over to <a href=\"http://palo-alto.edu\">http://palo-alto.edu</a>, enter in your username and password as you normally would for Schoology, click \"Google Apps\", go to Gmail, and click on your profile on the top right corner of Gmail. This would show your @palo-alto.org email. For help with this, or if you go to a PAUSD school, but don't have an @palo-alto.edu account, please contact support@theteknet.com</font>";
}
elseif($email==null){
    echo "Enter your @palo-alto.edu email and your name.";
}

else{
    echo "Gotcha, we will be contacting you at $email shortly. To unsubscribe, just send an email to support@theteknet.org with the word \"Unsubscribe\" in the subject line, and we will be more then happy to remove your email from recieving updates";
    
mysqli_query($con,"INSERT INTO userinfo (email, name) VALUES ('$email','$name')");
}
			
?>
</section>
			<section class="color-2">
			<h1>What is TekNet?</h1>
			TekNet is a social network created by a group of Gunn studends designed for ALL PAUSD students ages 13+. TekNet will help PAUSD students connect, make friends (especially new students), find common classes, and get help with homework.
			</section>
						<section class="color-3">
			<h1>When is TekNet going to be released?</h1>
			TekNet has no public release schedule at this time. TekNet's release depends on the demand of users that have pre-registered. If we receive at least 45 pre-registration requests, we will be released around late December to early January.
			</section>
			<section class="color-4">
			<h1>I heard TekNet is ad-free. How are you guys going to make money? How are you going to make enough money to support your own services?</h1>
			Simple answer: WE WON'T. Since TekNet is a startup, we are trying to get a high userbase before we start making any money
			</section>
						</section>
			<section class="color-5">
			<h1>I want to help build your website</h1>
			For volunteering, you can email admin@theteknet.org. Don't forget to mention your skills. We are looking for Security experts (Able to divert a SQL injection), SQL experts, and people willing to switch with the founder to go on a night-shift. You can also fork us on <a href = "https://github.com/kirill2485/TekNet">GitHub</a>.
			</section>
</body>
</html>