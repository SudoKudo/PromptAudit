<h1>Admin management</h1>

<p>The admin management tools allows you to add and remove administrators for clubs. The Club ID can be retrieved from the club management page. An email address is not used but can be provided for your own use. Passwords will be hashed and securely stored in the database. You can reset an administrator's password using the update function.</p>

<p>Note that if you delete and then re-add an administrator, the only information that will be deleted is the information on this page plus notes features (the textbox, categories, and comments shown on the <b>View Submissions</b> page in the application administration section.</p>

<?
if(isset($message) && $message != "") {
	echo "<p class=\"message\">$message</p>";
}
?>

<form action="man_admins.php?action=add" method="post">
<table align="center" class="borderon" bgcolor=#F2F5F7>
<tr>
	<td align="right"><p class="admin_table_entry">Admin username</p></td>
	<td><input type="text" name="username" style="width:100%"></td>
</tr>
<tr>
	<td align="right"><p class="admin_table_entry">Club</p></td>
	<td><select name="club_id">
		<?
			foreach($clubsList as $club_id => $club_name) {
				echo "<option value=\"" . $club_id . "\">" . $club_name . "</option>";
 			}
		?>
		<option value="0">General Application</option>
	</select></td>
</tr>
<tr><td align="right" colspan="2"><input type="submit" value="Add admin"></td></tr>
</table>
</form><br><br>

<table width=100%>
<tr>
	
	<th><p class="admin_table_header">Username</p></th>
	<th><p class="admin_table_header">Club</p></th>
	<th><p class="admin_table_header">Update</p></th>
	<th><p class="admin_table_header">Remove</p></th>
</tr>

<?
foreach($adminList as $item) {
?>
	<form method="post" action="man_admins.php">
	<input type="hidden" name="id" value="<?= $item[0] ?>">
	<input type="hidden" name="club_id_orig" value="<?= $item[1] ?>">
	<tr>
		<td><input type="text" name="username" value="<?= $item[2] ?>" style="width:100%"></td>
		<td><select name="club_id" style="width:100%">
						<option value="<?= $item[1] ?>">
			<?
				if ($item[1] == 0) {
				   echo "General Application";
				} else {
					 echo $clubsList[$item[1]];
				}
			?>
			</option>
				<?
				foreach($clubsList as $club_id => $club_name) {
					echo "<option value=\"" . $club_id . "\">" . $club_name . "</option>";
 				}
 				
 				echo "<option value=\"0\">General Application</option>";
				?>
</select>
</td>
		<td><input type="submit" name="action" value="update"></td>
		<td><input type="submit" name="action" value="remove"></td>
	</tr>
	</form>
<?
}
?>

</table>
