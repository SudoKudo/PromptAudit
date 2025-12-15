require 'spec_helper'

describe HelpersController, type: :controller do

  describe 'POST #html_renderer' do
    context 'without session cookie' do
      it 'redirects to root_path' do
        post 'html_renderer', content: '<div>Hello', format: :html
        expect(response).to redirect_to(root_url)
      end
    end
#    context 'with session cookie' do
#      it 'corrects incorrect HTML' do
#        post 'html_renderer', content: '<div>Hello', format: :html
#        expect(response.body).to eq('<div>Hello</div>')
#      end
#    end
  end
end
