import { ProfileIcon } from "components/ProfilePage/StyledUserIcons"
import { NavProps, TabContent } from "react-bootstrap"
import styled from "styled-components"
import { Nav } from "../bootstrap"

export const StyledTabNav = styled(Nav).attrs(props => ({
  className: props.className
}))`
  display: flex;
  flex-wrap: nowrap;

  height: 2.5em;
  margin-bottom: 1rem;

  .nav-item {
    flex-grow: 1;
    width: auto;
  }

  text-align: center;
  font-family: Nunito;
  font-size: 1.25rem;
  color: var(--bs-dark);

  .nav-link.active {
    color: #c71e32;
  }

  .nav-link {
    cursor: pointer;
    overflow: visible;
    width: auto;
    margin: 0 1rem;
  }

  .nav-link:first-child {
    margin-left: 0;
  }

  @media (width < 768px) {
    flex-direction: column;

    .nav-item {
      width: 100%;
      flex-grow: 0;
    }

    .nav-link {
      margin: 0;
    }
  }
`

export const TabNavWrapper = ({ children, className, ...props }: NavProps) => {
  return (
    <Nav
      className={`d-flex w-100 flex-column flex-lg-row flex-lg-nowrap mb-3 text-center h3 color-dark ${className}`}
      {...props}
    >
      {children}
    </Nav>
  )
}

const TabNavLink = styled(Nav.Link).attrs(props => ({
  className: `rounded-top m-0 p-0 ${props.className}`
}))`
  &.active {
    color: #c71e32;
  }
`

export const TabNavItem = ({
  tab,
  i: i,
  className
}: {
  tab: TabType
  i: number
  className?: string
}) => {
  return (
    <Nav.Item className={`flex-lg-fill ${className}`} key={tab.eventKey}>
      <TabNavLink eventKey={tab.eventKey} className={`rounded-top m-0 p-0`}>
        <p className={`my-0 text-nowrap ${i === 0 ? "" : "mx-4"}`}>
          {tab.title}
        </p>
        <hr className={`my-0`} />
      </TabNavLink>
    </Nav.Item>
  )
}
export type TabType = { title: string; eventKey: string; content: JSX.Element }
export const StyledTabContent = styled(TabContent)`
  margin-top: 3.5rem;
  z-index: -1;

  @media (min-width: 329px) {
    margin-top: 2rem;
  }

  @media (min-width: 517px) {
    margin-top: -0.5rem;
  }
`
export const OrgIconSmall = styled(ProfileIcon).attrs(props => ({
  className: props.className,
  role: "organization"
}))`
  height: 3rem;
  width: 3rem;
  margin: 1rem;
`
