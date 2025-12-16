class UploadedFilesController < ApplicationController
  add_breadcrumb 'Files', :uploaded_files_path
  before_action :set_uploaded_file, only: [:show, :edit, :update, :destroy]
  before_action :signed_in_user, only: [:show, :index, :edit, :update, :new, :create, :destroy]

  # GET /uploaded_files
  # GET /uploaded_files.json
  def index
    @set_title = true
    @uploaded_files = UploadedFile.all
  end

  # GET /uploaded_files/1
  # GET /uploaded_files/1.json
  def show
  end

  # GET /uploaded_files/new
  def new
    @uploaded_file = UploadedFile.new
    add_breadcrumb 'New', new_uploaded_file_path
  end

  # GET /uploaded_files/1/edit
  def edit
    add_breadcrumb 'Edit', edit_uploaded_file_path
  end

  # POST /uploaded_files
  # POST /uploaded_files.json
  def create
    @uploaded_file = UploadedFile.new(uploaded_file_params)
    uploaded_io = params[:uploaded_file][:content]

    # Set the file name to the remote one, if not set by :name form field
    @uploaded_file.name = uploaded_io.original_filename if @uploaded_file.name == ''

    # Just to be sure, replace every whitespace with a '-'
    @uploaded_file.name.gsub!(/ /, '-')

    # Then write to file
    # WARNING : File.open is definitely vulnerable to Path Traversal Attacks
    # (https://www.owasp.org/index.php/Path_Traversal) 
    # The following line should take care of it, by only taking the past part of the path (aka filename)
    @uploaded_file.name = @uploaded_file.name.split(/\//)[-1]

    File.open(@uploaded_file.absolute_path, 'wb') do |file|
      file.write(uploaded_io.read)
    end

    respond_to do |format|
      if @uploaded_file.save
        format.html { redirect_to @uploaded_file, notice: 'Uploaded file was successfully created.' }
        format.json { render :show, status: :created, location: @uploaded_file }
      else
        format.html { render :new }
        format.json { render json: @uploaded_file.errors, status: :unprocessable_entity }
      end
    end
  end

  # PATCH/PUT /uploaded_files/1
  # PATCH/PUT /uploaded_files/1.json
  def update
    respond_to do |format|
      old_name = @uploaded_file.name
      if @uploaded_file.update(uploaded_file_params)
        format.html do
          File.rename(absolute_path_for(old_name), @uploaded_file.absolute_path) if old_name != @uploaded_file.name
          redirect_to @uploaded_file, notice: 'Uploaded file was successfully updated.'
        end
        format.json { render :show, status: :ok, location: @uploaded_file }
      else
        format.html { render :edit }
        format.json { render json: @uploaded_file.errors, status: :unprocessable_entity }
      end
    end
  end

  # DELETE /uploaded_files/1
  # DELETE /uploaded_files/1.json
  def destroy
    path_to_file = @uploaded_file.absolute_path
    File.delete(path_to_file) if File.exist?(path_to_file)
    @uploaded_file.destroy
    respond_to do |format|
      format.html { redirect_to uploaded_files_url, notice: 'Uploaded file was successfully destroyed.' }
      format.json { head :no_content }
    end
  end

  private

  # Use callbacks to share common setup or constraints between actions.
  def set_uploaded_file
    @uploaded_file = UploadedFile.find(params[:id])
    add_breadcrumb @uploaded_file.name, @uploaded_file
  end

  # Never trust parameters from the scary internet, only allow the white list through.
  def uploaded_file_params
    params.require(:uploaded_file).permit(:name, :extract)
  end

  def absolute_path_for(file_name)
    Rails.root.join('public', 'uploads', file_name)
  end
end
