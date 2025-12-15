require 'spec_helper'

describe UploadedFilesController, type: :controller do
  it 'has a valid factory' do
    expect( FactoryGirl.create(:uploaded_file)).to be_valid
  end

  it 'does not accept relative paths in file name'
end
