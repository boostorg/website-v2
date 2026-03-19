import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Code Blocks",
};

const CODE_BEAST = `int main()
{
    net::io_context ioc;
    tcp::resolver resolver(ioc);
    beast::tcp_stream stream(ioc);

    stream.connect(resolver.resolve("example.com", "80"));

    http::request<http::empty_body> req{http::verb::get, "/", 11};
    req.set(http::field::host, "example.com");

    http::write(stream, req);

    beast::flat_buffer buffer;
    http::response<http::string_body> res;
    http::read(stream, buffer, res);

    std::cout << res << std::endl;
}`;

const CODE_HELLO = `#include <iostream>
int main()
{
    std::cout << "Hello, Boost.";
}`;

const CODE_INSTALL = `brew install openssl

export OPENSSL_ROOT=$(brew --prefix openssl)

# Install bjam tool user config: https://www.bfgroup.xyz/b2/manual/release/index.html
cp ./libs/beast/tools/user-config.jam $HOME`;

export const AllVariants = () => (
  <Pattern
    template="v3/includes/_code_blocks_story.html"
    context={{
      code_standalone_1: CODE_BEAST,
      code_standalone_2: CODE_BEAST,
      code_card_1: CODE_HELLO,
      code_card_2: CODE_BEAST,
      code_card_3: CODE_INSTALL,
    }}
  />
);
