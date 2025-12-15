package banco_de_dados.dbo;

public class Aluno {
	private String RA,nome,email,telefone,endereco,responsavel;
	
	public Aluno(String RA,String nome,String email,String telefone,String endereco,String responsavel)throws Exception{
		if(RA.length()> 5 || RA.length() < 5){
			throw new Exception("RA invalido");
		}
		
		if(!numerico(RA)){
			throw new Exception("O RA deve conter apenas numeros");
		}
		if(!numerico(telefone)){
			throw new Exception("O telefone deve conter apenas numeros");
		}		
		
		this.RA = RA.replace("'", "");
		this.nome = nome.replace("'", "");;
		this.email = email.replace("'", "");;
		this.telefone = telefone.replace("'", "");;
		this.endereco = endereco.replace("'", "");;
		this.responsavel = responsavel.replace("'", "");;
	}
	
	private boolean numerico(final String s){
		try{
			Float.valueOf(s);
			return true;
		}catch(Exception e){
			return false;
		}
	}
	
	public String getRA(){
		return this.RA;
	}
	
	public String getNome(){
		return this.nome;
	}
	
	public String getEmail(){
		return this.email;
	}
	
	public String getTelefone(){
		return this.telefone;
	}
	
	public String getEndereco(){
		return this.endereco;
	}
	
	public String getResponsavel(){
		return this.responsavel;
	}
}
