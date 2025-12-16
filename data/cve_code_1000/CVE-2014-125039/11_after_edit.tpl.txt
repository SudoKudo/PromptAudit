<?php echo $this->fetch("header"); ?>
<div id="content">
  <div class="container relative">
    <div class="panel">
      <div class="buttons">
        <a href="panel.php?type=pages&page=<?php echo $this->currentPage; ?>">Manage Page</a>
        <a href="panel.php?type=pages&action=edit&pageid=<?php echo $this->pageData['Id']; ?>&page=<?php echo $this->currentPage; ?>" class="active">Edit Page</a>
      </div>
        
      <form action="panel.php?type=pages&action=edit&pageid=<?php echo $this->pageData['Id']; ?>&page=<?php echo $this->currentPage; ?>" method="post">
        <table class="pagesForm">
          <tr>
            <td>Title:</td>
            <td><input type="text" name="pageTitle" value="<?php echo $this->pageData['Title']; ?>" /></td>
          </tr>
          <tr>
            <td>Category:</td> 
            <td>
              <select name="categoryId" style="width: 304px;padding: 5px;">
                <?php foreach($this->categoryList AS $key => $value) { ?>
                  <option value="<?php echo $key; ?>" <?php if($this->pageData['CategoryId'] == $key) echo "selected='selected'"; ?>>
                    <?php echo $value; ?>
                  </option> 
                <?php } ?>
              </select>
            </td>
          </tr>
          <tr>
            <td>Body:</td>
            <td><textarea name="pageBody"><?php echo $this->pageData['Body']; ?></textarea></td>
          </tr>
          <tr>
            <td></td>
            <td><input type="submit" name="submit_regenerate" value="Regenerate Sentences" style="width: 150px; float: right;" /> <input type="submit" name="submit_editcat" value="Edit Category" style="width: 100px; float: right;margin-right: 12px;" /></td>
            
          </tr>
        </table>
      </form>
    </div>
  </div>
</div>
<?php echo $this->fetch("footer"); ?>