require 'faker'

FactoryGirl.define do
  factory :uploaded_file do |f|
    f.name 'hello.png'
  end

  factory :dangerous_file, class: UploadedFile do |f|
    f.name '../Hello.png'
  end
end
