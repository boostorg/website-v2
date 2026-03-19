import React from "react";
import { Pattern } from "storybook-django/src/react";

export default {
  title: "Components/Post Cards List",
};

const PostCard = (props) => (
  <Pattern template="v3/includes/_post_card_v3.html" context={props} />
);

const ButtonPattern = (props) => (
  <Pattern template="v3/includes/_button.html" context={props} />
);

export const Default = () => (
  <section className="post-cards post-cards--default post-cards--neutral post-cards--vertical">
    <h2 className="post-cards__heading">
      <a href="#" className="post-cards__heading-link">
        Posts from the Boost community
      </a>
    </h2>
    <ul className="post-cards__list">
      <li className="post-cards__item">
        <PostCard
          post_title="A talk by Richard Thomson at the Utah C++ Programmers Group"
          post_url="#"
          post_date="03/03/2025"
          post_category="Issues"
          post_tag="beast"
          author_name="Richard Thomson"
          author_role="Contributor"
          author_show_badge={true}
          author_avatar_url="https://ui-avatars.com/api/?name=Richard+Thomson&size=48"
        />
      </li>
      <li className="post-cards__item">
        <PostCard
          post_title="A talk by Richard Thomson at the Utah C++ Programmers Group"
          post_url="#"
          post_date="03/03/2025"
          post_category="Issues"
          post_tag="beast"
          author_name="Peter Dimov"
          author_role="Maintainer"
          author_show_badge={true}
          author_avatar_url="https://ui-avatars.com/api/?name=Peter+Dimov&size=48"
        />
      </li>
      <li className="post-cards__item">
        <PostCard
          post_title="Boost.Bind and modern C++: a quick overview"
          post_url="#"
          post_date="15/02/2025"
          post_category="Releases"
          post_tag="bind"
          author_name="Alex Morgan"
          author_role="Contributor"
          author_show_badge={false}
          author_avatar_url="https://thispersondoesnotexist.com/"
        />
      </li>
    </ul>
    <div className="card__cta_section">
      <ButtonPattern label="View all posts" url="#" />
    </div>
  </section>
);
