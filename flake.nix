{
  description = "Boost.org development environment.";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils, ... }@inputs:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };
        # https://nixos.wiki/wiki/Google_Cloud_SDK
        gdk = pkgs.google-cloud-sdk.withExtraComponents( with pkgs.google-cloud-sdk.components; [
            gke-gcloud-auth-plugin
          ]);
        # Install a Ruby gem from rubygems.org
        asciidoctorBoostGem = pkgs.stdenv.mkDerivation rec {
          pname = "asciidoctor-boost";
          version = "0.1.7";
          sha = "ce139448812a9848219ce4cdb521c83c16009406a9d16efbc90bb24e94a46c24";

          src = pkgs.fetchurl {
            url = "https://rubygems.org/downloads/${pname}-${version}.gem";
            sha256 = "${sha}";
          };
          dontUnpack = true;
          nativeBuildInputs = [ pkgs.ruby ];
          buildPhase = "true"; # Nothing to compile.
          installPhase = ''
            # Create a temporary gem directory
            mkdir -p $out
            # Set GEM_HOME to install gems locally under $out.
            export GEM_HOME=$out
            # Install the gem into GEM_HOME.
            ${pkgs.ruby}/bin/gem install ${src} --no-document --ignore-dependencies
          '';
          meta = {
            description = "Asciidoctor Boost Ruby Gem installed from rubygems.org";
            homepage = "https://rubygems.org/gems/asciidoctor-boost";
            license = "BSL-1.0";
          };
        };

      in {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # general system
            # e.g. this could contain docker client if we wanted that to be consistent,
            #  though we need the daemon on the host anyway so it's redundant
            # general project
            awscli
            gdk
            just
            kubectl
            opentofu
            # frontend
            nodejs_22 # matches Dockerfile, due for upgrade?
            yarn
            # backend
            asciidoctor
            asciidoctorBoostGem
            pre-commit
            python313 # matches Dockerfile, due for upgrade?
            python313.pkgs.black
            python313.pkgs.isort
            python313.pkgs.pip-tools
          ];
          # Host system installation workflow goes into the bootstrap justfile target.
          # Project specific installation and execution workflow should go here.
          shellHook = ''
            if [ ! -f .git/hooks/pre-commit ]; then
              pre-commit install
            fi
            if [ ! -d .venv ]; then
              python3.13 -m venv .venv
              . .venv/bin/activate
              pip install -r requirements.txt -r requirements-dev.txt
            else
              . .venv/bin/activate
            fi
            if [ ! -f .env ]; then
              cp env.template .env
              echo ".env created, you should update its contents"
            fi
            # google cloud login
            gcloud auth list --format="value(account)" | grep -q . || {
              echo "Not logged in. Running gcloud auth login..."
              gcloud auth login
            }
          '';
        };
      }
    );
}
