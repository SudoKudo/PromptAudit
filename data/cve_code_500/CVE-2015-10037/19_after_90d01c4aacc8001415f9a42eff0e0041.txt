package banco_de_dados.dbo;

public class Responsavel {
	private String email, nome, telefone,endereco;
	
	public Responsavel(String email, String nome, String telefone, String endereco)throws Exception{
		if(!numerico(telefone)){
			throw new Exception("O telefone deve conter apenas numeros");
		}
		
		if(email == null || nome == null || telefone == null || endereco == null){
			throw new Exception("Os valores no podem ser nulos");
		}
		
		this.email = email;
		this.nome = nome;
		this.telefone = telefone;
		this.endereco = endereco;
		
	}
	
	private boolean numerico(final String s){
		try{
			Float.valueOf(s);
			return true;
		}catch(Exception e){
			return false;
		}
	}
	
	public String getEmail(){
		return this.email;
	}
	
	public String getNome(){
		return this.nome;
	}
	
	public String getTelefone(){
		return this.telefone;
	}
	
	public String getEndereco(){
		return this.endereco;
	}
}
