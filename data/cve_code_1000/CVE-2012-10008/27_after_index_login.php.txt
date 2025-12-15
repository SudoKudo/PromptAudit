<h1>Administrator Page</h1>

<p>Use the form below to log in to the club administration area.</p>

<table>
	<tr>
		<form method="POST" action="index.php">
		<table>
			<? if(!$user_loggedin) { ?>
			<tr>
				<td>Username:</td>
				<td><input type="text" name="username"/></td>
			</tr>
			<? } ?>
			<tr>
				<td>Password:</td>
				<td><input type="password" name="password"/></td>
			</tr>
			<tr>
				<td>Club:</td>
				<td><select name="club">
				<? foreach($clubs as $club_id => $club_name) { ?>
					<option value="<?= $club_id ?>"><?= $club_name ?></option>
				<? } ?>
				</select></td>
			</tr>
			<tr>
				<td colspan="2"><input type="submit" value="Submit" align="center"/></td>
			</tr>
		</table>
		</form>
	</tr>

	<?
	if(isset($message) && $message != "") {
	?>
		<tr><td colspan="2"><?= $message ?></td></tr>
	<?
	}
	?>
</table>
